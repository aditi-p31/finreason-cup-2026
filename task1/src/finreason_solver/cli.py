# SPDX-License-Identifier: Apache-2.0
"""Single entry point: build solvers, predict, score and package.

    python -m finreason_solver all      # regenerate everything end to end
"""

from __future__ import annotations

import argparse
import collections
import importlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from . import build_solvers, config, dataio, official
from .fallback import FallbackSolver, fit as fit_fallback
from .predict import predict_split, write_predictions
from .shapes import ShapeIndex

HIDDEN_FORMS_HELP = (
    "answer questions the shape index leaves unmatched with the optional "
    "per-template forms in finreason_solver.hiddenforms (off by default; not "
    "part of the default release; FINREASON_HIDDEN_FORMS=1 does the same)"
)
# The commands that read --hidden-forms / FINREASON_HIDDEN_FORMS.
HIDDEN_FORMS_COMMANDS = frozenset({"predict", "score-dev", "package", "all"})

SPLITS = {
    "dev": dataio.load_dev,
    "leaderboard": dataio.load_leaderboard,
    "test": dataio.load_test,
    "train": dataio.load_train,
}


def _emit(payload: Any) -> None:
    print(json.dumps(payload, indent=1, sort_keys=True, default=str))


def cmd_build_solvers(args: argparse.Namespace) -> int:
    if getattr(args, "single_stage", False):
        payloads = build_solvers.build(depth=args.depth, workers=args.workers)
    else:
        payloads = build_solvers.build_two_stage(
            depth=args.depth, workers=args.workers
        )
    path = build_solvers.save(payloads)
    shippable = [item for item in payloads if build_solvers.is_shippable(item)]
    summary = {
        "solvers_path": str(path),
        "templates": len(payloads),
        "validated": len(shippable),
        "unvalidated": len(payloads) - len(shippable),
        "errors": sum(1 for item in payloads if item.get("error")),
    }
    (config.ARTIFACTS / "build_summary.json").write_text(
        json.dumps(summary, indent=1, sort_keys=True)
    )
    _emit(summary)
    # A template whose derivation raised is recorded as an ``error`` payload
    # rather than aborting the pool; the build as a whole has still failed.
    return 1 if summary["errors"] else 0


def cmd_apply_genforms(args: argparse.Namespace) -> int:
    """Run stage 4 against an existing solvers.json, in place.

    The three search stages are the expensive part of the build; the
    generator-recovered forms are a table lookup plus one contract test each,
    so they can be applied to an already-built artifact without paying for a
    full rebuild.  ``build-solvers`` runs the same pass at the end of its own
    build, so the two routes agree.
    """

    payloads = json.loads(config.SOLVERS_JSON.read_text())
    by_id = {payload["template_id"]: payload for payload in payloads}
    before = sum(1 for item in by_id.values() if build_solvers.is_shippable(item))
    applied = build_solvers.apply_generator_forms(by_id)
    # Stage 5 runs in the same pass so this command and ``build-solvers``
    # still reach the same artifact.
    fixed = build_solvers.apply_reference_forms(by_id)
    updated = sorted(by_id.values(), key=lambda item: item["template_id"])
    path = build_solvers.save(updated)
    after = sum(1 for item in updated if build_solvers.is_shippable(item))
    _emit(
        {
            "solvers_path": str(path),
            "templates": len(updated),
            "validated_before": before,
            "validated_after": after,
            "applied": applied,
            "reference_fixes": fixed,
        }
    )
    return 0


def cmd_build_index(args: argparse.Namespace) -> int:
    index = ShapeIndex.build()
    path = index.save()
    _emit(
        {
            "shape_index_path": str(path),
            "exact_keys": len(index.exact),
            "loose_keys": len(index.loose),
            "conflicts": len(index.conflicts),
        }
    )
    return 0


def cmd_build_fallback(args: argparse.Namespace) -> int:
    model = fit_fallback(dataio.labelled_instances())
    path = model.save()
    _emit(
        {
            "fallback_path": str(path),
            "slot_priors": len(model.slot_priors),
            "final_priors": len(model.final_priors),
        }
    )
    return 0


def _hidden_forms_on(args: argparse.Namespace) -> bool:
    """``--hidden-forms`` (before or after the command) or FINREASON_HIDDEN_FORMS=1."""

    return bool(getattr(args, "hidden_forms", False)) or config.HIDDEN_FORMS


def _hidden_forms_available() -> bool:
    """Whether this build carries the module (located, not imported)."""

    return importlib.util.find_spec(f"{__package__}.hiddenforms") is not None


def _require_hidden_forms() -> None:
    if not _hidden_forms_available():
        raise SystemExit(
            "--hidden-forms: finreason_solver.hiddenforms is not part of this release"
        )


def _load_hidden_forms():
    _require_hidden_forms()
    return importlib.import_module(f"{__package__}.hiddenforms").HiddenForms.load()


def _predict(
    split_name: str,
    out: Path,
    use_fallback: bool = True,
    use_hidden_forms: bool = False,
):
    split = SPLITS[split_name]()
    index = ShapeIndex.load()
    solvers = build_solvers.load()
    fallback = FallbackSolver.load() if use_fallback else None
    hidden_forms = _load_hidden_forms() if use_hidden_forms else None
    records, matches = predict_split(split, solvers, index, fallback, hidden_forms)
    write_predictions(records, out)
    method_counts = collections.Counter(match.method for match in matches.values())
    covered = sum(
        1
        for match in matches.values()
        if match.template_id and match.template_id in solvers
    )
    answered = sum(1 for record in records if record["final_answer"] is not None)
    slots_emitted = sum(len(record["steps"]) for record in records)
    slots_total = sum(
        len(split.questions[record["case_id"]]["trace_spec"]["slots"])
        for record in records
    )
    summary = {
        "split": split_name,
        "predictions_path": str(out),
        "cases": len(records),
        "match_methods": dict(method_counts),
        "cases_with_validated_solver": covered,
        "cases_with_final_answer": answered,
        "slots_emitted": slots_emitted,
        "slots_expected": slots_total,
    }
    if hidden_forms is not None:
        summary["hidden_forms"] = hidden_forms.last_report
    return summary


def cmd_predict(args: argparse.Namespace) -> int:
    out = Path(args.out) if args.out else config.ARTIFACTS / f"{args.split}_predictions.jsonl"
    summary = _predict(
        args.split,
        out,
        use_fallback=not args.no_fallback,
        use_hidden_forms=_hidden_forms_on(args),
    )
    _emit(summary)
    return 0


def cmd_score_dev(args: argparse.Namespace) -> int:
    out = config.ARTIFACTS / "dev_predictions.jsonl"
    summary = _predict(
        "dev",
        out,
        use_fallback=not args.no_fallback,
        use_hidden_forms=_hidden_forms_on(args),
    )
    report = official.score_dev(out)
    payload = {"coverage": summary, "official_score_dev": report}
    (config.ARTIFACTS / "dev_score.json").write_text(
        json.dumps(payload, indent=1, sort_keys=True)
    )
    _emit(payload)
    return 0 if report.get("_exit_code") == 0 else 2


def cmd_package(args: argparse.Namespace) -> int:
    questions = {
        "leaderboard": config.LB_QUESTIONS,
        "test": config.TEST_QUESTIONS,
    }[args.split]
    predictions = config.ARTIFACTS / f"{args.split}_predictions.jsonl"
    summary = _predict(
        args.split,
        predictions,
        use_fallback=not args.no_fallback,
        use_hidden_forms=_hidden_forms_on(args),
    )
    output = config.ARTIFACTS / f"{args.split}_submission.zip"
    # The organiser packager refuses to overwrite, so a rerun must clear the
    # previous archive or it would silently admit a stale one.
    if output.exists():
        output.unlink()
    packaged = official.package(questions, predictions, output)
    payload: dict[str, Any] = {"coverage": summary, "official_package": packaged}
    if args.split == "leaderboard":
        payload["official_leaderboard_admit"] = official.leaderboard_admit(
            questions, config.LB_EXPECTED_IDS, output
        )
    (config.ARTIFACTS / f"{args.split}_package.json").write_text(
        json.dumps(payload, indent=1, sort_keys=True)
    )
    _emit(payload)
    ok = packaged.get("_exit_code") == 0
    if args.split == "leaderboard":
        ok = ok and payload["official_leaderboard_admit"].get("_exit_code") == 0
    return 0 if ok else 2


def cmd_all(args: argparse.Namespace) -> int:
    """Run every stage in order and stop at the first one that fails.

    A failed stage leaves later inputs stale (packaging after a failed build
    would archive the previous solvers), so the run stops there and returns
    that stage's non-zero exit code.
    """

    stages: list[tuple[str, Any]] = [
        ("build-index", lambda: cmd_build_index(args)),
        ("build-solvers", lambda: cmd_build_solvers(args)),
        ("build-fallback", lambda: cmd_build_fallback(args)),
        ("score-dev", lambda: cmd_score_dev(args)),
    ]
    for split in ("leaderboard", "test"):
        namespace = argparse.Namespace(
            split=split,
            no_fallback=args.no_fallback,
            hidden_forms=getattr(args, "hidden_forms", False),
        )
        stages.append(
            (f"package --split {split}", lambda namespace=namespace: cmd_package(namespace))
        )
    for name, run in stages:
        code = run()
        if code != 0:
            print(
                f"finreason_solver all: stage '{name}' failed with exit code "
                f"{code}; later stages were not run",
                file=sys.stderr,
            )
            return code
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="finreason_solver", description=__doc__)
    parser.add_argument("--no-fallback", action="store_true")
    # Left out of --help in a build without the module; main() refuses it there.
    hidden_forms_help = (
        HIDDEN_FORMS_HELP if _hidden_forms_available() else argparse.SUPPRESS
    )
    parser.add_argument(
        "--hidden-forms", action="store_true", help=hidden_forms_help
    )
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build-solvers")
    build.add_argument("--depth", type=int, default=2)
    build.add_argument("--workers", type=int, default=None)
    build.add_argument("--single-stage", action="store_true")
    build.set_defaults(handler=cmd_build_solvers)

    genforms = commands.add_parser("apply-genforms")
    genforms.set_defaults(handler=cmd_apply_genforms)

    index = commands.add_parser("build-index")
    index.set_defaults(handler=cmd_build_index)

    fallback = commands.add_parser("build-fallback")
    fallback.set_defaults(handler=cmd_build_fallback)

    predict = commands.add_parser("predict")
    predict.add_argument("--split", choices=sorted(SPLITS), required=True)
    predict.add_argument("--out", default=None)
    predict.set_defaults(handler=cmd_predict)

    score = commands.add_parser("score-dev")
    score.set_defaults(handler=cmd_score_dev)

    package = commands.add_parser("package")
    package.add_argument("--split", choices=("leaderboard", "test"), required=True)
    package.set_defaults(handler=cmd_package)

    everything = commands.add_parser("all")
    everything.add_argument("--depth", type=int, default=2)
    everything.add_argument("--workers", type=int, default=None)
    everything.add_argument("--single-stage", action="store_true")
    everything.set_defaults(handler=cmd_all)

    # Also accepted after the command (so `./run.sh --hidden-forms` works).
    # SUPPRESS keeps an absent subcommand flag from resetting the global one.
    for sub in (predict, score, package, everything):
        sub.add_argument(
            "--hidden-forms",
            action="store_true",
            default=argparse.SUPPRESS,
            help=hidden_forms_help,
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # Refuse the route before any stage runs: in a build without the module,
    # `all` would otherwise rebuild (and overwrite) every artifact first.
    if args.command in HIDDEN_FORMS_COMMANDS and _hidden_forms_on(args):
        _require_hidden_forms()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())

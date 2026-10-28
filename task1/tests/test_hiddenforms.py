# SPDX-License-Identifier: Apache-2.0
"""The optional per-template route for unmatched questions (``--hidden-forms``).

Router: every test question the shape index leaves unmatched routes to exactly
one packaged form, no matched question of any split routes to one, and the
routing reproduces the grouping of ``hidden/templates.json``.

Identity: with the route off, the dev, leaderboard and test predictions are
byte-identical to the shipped ones (14 Sep 2026); with it on, the test
predictions and the organisers' archive are byte-identical to the ranked
submission accepted on 21 Oct 2026, and dev and leaderboard do not change.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

hiddenforms = pytest.importorskip("finreason_solver.hiddenforms")

from finreason_solver import build_solvers, cli, config, dataio, official  # noqa: E402
from finreason_solver.fallback import FallbackSolver  # noqa: E402
from finreason_solver.numbers import question_body  # noqa: E402
from finreason_solver.predict import predict_split, write_predictions  # noqa: E402
from finreason_solver.shapes import ShapeIndex  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HIDDEN = ROOT / "hidden"
ACCEPTED_20261021 = ROOT / "accepted_20261021" / "test_predictions.jsonl"

# Shipped predictions (README "Expected outputs"; the 14 Sep 2026 content).
OFF_SHA256 = {
    "dev": "eda131683572461613240c8bda541a9641b208e30c2de7d65418860809c13a8c",
    "leaderboard": "e079900c213fe463e353a2c6900da51ead5da8a18181fae158fe37ac9ed5c634",
    "test": "d1007b775c5b047712d540dfbeb4156177fa19b8216390028d7a0855a1db0828",
}
# The test submission accepted on 2026-10-21 (predictions and archive; ranked).
ON_TEST_SHA256 = "3f0bec6f039e66b49365af039ab0ab41902c3274dab43b8d02fb3c6a16c4a2d4"
ON_TEST_ZIP_SHA256 = "b786d1e5b8b7284b762e8dbbd2248692cfe4af87348d69f1eb8f464a85dc0991"

N_TEMPLATES = 116
N_HIDDEN = 348

needs_solvers = pytest.mark.skipif(
    not config.SOLVERS_JSON.exists(),
    reason="run `python -m finreason_solver build-solvers` first",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_file(path: Path, name: str):
    saved = sys.dont_write_bytecode
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved  # the hidden/ scripts switch it on
    return module


@pytest.fixture(scope="module")
def router():
    return hiddenforms.HiddenForms.load()


@pytest.fixture(scope="module")
def routes_payload() -> dict:
    return json.loads(hiddenforms.ROUTES_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def index() -> ShapeIndex:
    if config.SHAPE_INDEX_JSON.exists():
        return ShapeIndex.load(config.SHAPE_INDEX_JSON)
    return ShapeIndex.build()


@pytest.fixture(scope="module")
def test_split():
    return dataio.load_test()


@pytest.fixture(scope="module")
def unmatched(index, test_split) -> dict[str, dict]:
    return {
        case_id: question
        for case_id, question in sorted(test_split.questions.items())
        if index.identify(question["question"]).template_id is None
    }


# -- packaging -------------------------------------------------------------
def test_packaged_forms_are_pinned_and_complete(router, routes_payload) -> None:
    forms = routes_payload["forms"]
    assert len(forms) == N_TEMPLATES
    assert sorted(router.solvers) == sorted(forms)
    assert len(router.routes) == N_TEMPLATES  # one distinct shape per template
    packaged = sorted(path.stem for path in hiddenforms.FORMS_DIR.glob("*.py"))
    assert packaged == sorted(forms)
    for key, entry in forms.items():
        assert _sha256(hiddenforms.FORMS_DIR / f"{key}.py") == entry["sha256"], key
    assert _sha256(hiddenforms.HELPER) == routes_payload["helper"]["sha256"]


@pytest.mark.skipif(not (HIDDEN / "forms" / "final").is_dir(), reason="hidden/forms/final not present")
def test_packaged_forms_are_byte_copies_of_the_reviewed_forms(routes_payload) -> None:
    final = HIDDEN / "forms" / "final"
    reviewed = sorted(path.stem for path in final.glob("H[0-9][0-9][0-9].py"))
    assert reviewed == sorted(routes_payload["forms"])
    for key in reviewed:
        assert (hiddenforms.FORMS_DIR / f"{key}.py").read_bytes() == (final / f"{key}.py").read_bytes(), key
    assert hiddenforms.HELPER.read_bytes() == (HIDDEN / "hlib.py").read_bytes()


@pytest.mark.skipif(not (HIDDEN / "templates.json").exists(), reason="hidden/templates.json not present")
def test_export_reports_the_package_copy_up_to_date() -> None:
    done = subprocess.run(
        [sys.executable, str(HIDDEN / "export_forms.py"), "--check"],
        capture_output=True, text=True, timeout=300, check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert json.loads(done.stdout)["up_to_date"] is True


def test_a_modified_form_is_refused(tmp_path) -> None:
    copy = tmp_path / "hiddenforms"
    shutil.copytree(hiddenforms.HERE, copy, ignore=shutil.ignore_patterns("__pycache__"))
    target = copy / "forms" / "H009.py"
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(hiddenforms.FormIntegrityError, match="H009"):
        hiddenforms.HiddenForms.load(copy / "routes.json")


def test_loading_leaves_no_hlib_module_behind() -> None:
    before = sys.modules.get("hlib")
    hiddenforms.HiddenForms.load()
    assert sys.modules.get("hlib") is before


@pytest.mark.skipif(not (HIDDEN / "run_forms.py").exists(), reason="hidden/run_forms.py not present")
def test_packaged_forms_pass_the_form_lint() -> None:
    run_forms = _load_file(HIDDEN / "run_forms.py", "_hf_run_forms")
    for path in sorted(hiddenforms.FORMS_DIR.glob("*.py")):
        errors, _warnings = run_forms.lint_source(path.read_text())
        assert errors == [], (path.name, errors)


# -- routing ---------------------------------------------------------------
@pytest.mark.skipif(not (HIDDEN / "build_templates.py").exists(), reason="hidden/build_templates.py not present")
def test_route_key_is_the_template_grouping_rule(test_split) -> None:
    build_templates = _load_file(HIDDEN / "build_templates.py", "_hf_build_templates")
    for question in test_split.questions.values():
        text = question["question"]
        assert hiddenforms.bshape(text) == build_templates.bshape(text)


def test_every_unmatched_test_question_routes_to_exactly_one_form(
    unmatched, routes_payload, router
) -> None:
    assert len(unmatched) == N_HIDDEN
    per_key: dict[str, list[str]] = {}
    for case_id, question in unmatched.items():
        shape = hiddenforms.bshape(question["question"])
        hits = [key for key, entry in routes_payload["forms"].items() if entry["shape"] == shape]
        assert len(hits) == 1, (case_id, hits)
        assert router.route(question["question"]) == hits[0]
        per_key.setdefault(hits[0], []).append(case_id)
    assert sorted(per_key) == sorted(routes_payload["forms"])
    assert {len(ids) for ids in per_key.values()} == {3}


@pytest.mark.skipif(not (HIDDEN / "templates.json").exists(), reason="hidden/templates.json not present")
def test_routing_reproduces_the_template_grouping(unmatched, router) -> None:
    templates = json.loads((HIDDEN / "templates.json").read_text(encoding="utf-8"))["templates"]
    expected = {t["key"]: sorted(t["case_ids"]) for t in templates}
    routed: dict[str, list[str]] = {}
    for case_id, question in unmatched.items():
        routed.setdefault(router.route(question["question"]), []).append(case_id)
    assert {key: sorted(ids) for key, ids in routed.items()} == expected


def test_every_routed_form_answers_its_questions(unmatched, router) -> None:
    answers = router.answer_split(unmatched.values())
    assert sorted(answers) == sorted(unmatched)
    report = router.last_report
    assert report["templates_rejected"] == {}
    assert report["questions_answered"] == N_HIDDEN
    assert report["templates_answered"] == N_TEMPLATES
    assert report["slots_from_forms"] == 456
    for case_id, answer in answers.items():
        assert answer.key == router.route(unmatched[case_id]["question"])


@pytest.mark.parametrize(
    "loader", [dataio.load_train, dataio.load_dev, dataio.load_leaderboard, dataio.load_test]
)
def test_no_matched_question_routes_to_a_hidden_form(loader, index, router) -> None:
    for question in loader().questions.values():
        if index.identify(question["question"]).template_id is not None:
            assert router.route(question["question"]) is None, question["case_id"]


@needs_solvers
@pytest.mark.parametrize("loader", [dataio.load_dev, dataio.load_leaderboard])
def test_no_dev_or_leaderboard_question_reaches_the_forms(loader, index, router) -> None:
    predict_split(loader(), build_solvers.load(), index, FallbackSolver.load(), router)
    assert router.last_report["questions_routed"] == 0


@needs_solvers
def test_a_failing_form_sends_its_whole_template_to_the_fallback(
    unmatched, index, router, test_split, tmp_path
) -> None:
    key = "H009"
    victim = sorted(cid for cid, q in unmatched.items() if router.route(q["question"]) == key)[1]
    victim_body = question_body(unmatched[victim]["question"])
    good = router.solvers[key]

    def flaky(body):
        if body == victim_body:
            raise ValueError("simulated extraction failure")
        return good(body)

    broken = hiddenforms.HiddenForms(router.routes, {**router.solvers, key: flaky}, router.helper)
    solvers, fallback = build_solvers.load(), FallbackSolver.load()
    records_on, _ = predict_split(test_split, solvers, index, fallback, broken)
    records_off, _ = predict_split(test_split, solvers, index, fallback)
    assert list(broken.last_report["templates_rejected"]) == [key]
    assert broken.last_report["questions_answered"] == N_HIDDEN - 3
    by_on = {r["case_id"]: r for r in records_on}
    by_off = {r["case_id"]: r for r in records_off}
    for case_id, question in unmatched.items():
        if router.route(question["question"]) == key:
            assert by_on[case_id] == by_off[case_id], case_id


# -- the flag --------------------------------------------------------------
@pytest.mark.parametrize(
    "argv, env, expected",
    [
        (["predict", "--split", "test"], False, False),
        (["--hidden-forms", "predict", "--split", "test"], False, True),
        (["predict", "--split", "test", "--hidden-forms"], False, True),
        (["package", "--split", "test", "--hidden-forms"], False, True),
        (["score-dev", "--hidden-forms"], False, True),
        (["all", "--hidden-forms"], False, True),
        (["predict", "--split", "test"], True, True),
    ],
)
def test_flag_spellings(monkeypatch, argv, env, expected) -> None:
    monkeypatch.setattr(config, "HIDDEN_FORMS", env)
    assert cli._hidden_forms_on(cli.build_parser().parse_args(argv)) is expected


def _without_the_module(monkeypatch) -> None:
    """Make this build look like the default release (no hiddenforms module)."""

    real = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name, *a: None if name == "finreason_solver.hiddenforms" else real(name, *a),
    )


def _stub_handlers(monkeypatch) -> list[str]:
    """Replace every stage and command with a recorder; ``all`` runs the stubs."""

    calls: list[str] = []
    for name in (
        "cmd_build_index",
        "cmd_build_solvers",
        "cmd_build_fallback",
        "cmd_score_dev",
        "cmd_package",
        "cmd_predict",
    ):
        monkeypatch.setattr(cli, name, lambda args, name=name: calls.append(name) or 0)
    return calls


def test_flag_without_the_module_stops_with_a_clear_message(monkeypatch) -> None:
    _without_the_module(monkeypatch)
    with pytest.raises(SystemExit, match="not part of this release"):
        cli._load_hidden_forms()


@pytest.mark.parametrize(
    "argv, env",
    [
        (["all", "--hidden-forms"], False),
        (["--hidden-forms", "all"], False),
        (["all"], True),
        (["predict", "--split", "test", "--hidden-forms"], False),
        (["--hidden-forms", "score-dev"], False),
        (["package", "--split", "test"], True),
    ],
)
def test_flag_without_the_module_stops_before_any_stage(monkeypatch, argv, env) -> None:
    _without_the_module(monkeypatch)
    calls = _stub_handlers(monkeypatch)
    monkeypatch.setattr(config, "HIDDEN_FORMS", env)
    with pytest.raises(SystemExit, match="not part of this release"):
        cli.main(argv)
    assert calls == []


def test_flag_without_the_module_leaves_other_commands_alone(monkeypatch) -> None:
    _without_the_module(monkeypatch)
    calls = _stub_handlers(monkeypatch)
    monkeypatch.setattr(config, "HIDDEN_FORMS", True)
    assert cli.main(["build-index"]) == 0
    assert calls == ["cmd_build_index"]


@pytest.mark.parametrize("present", [True, False])
def test_help_lists_the_flag_only_when_the_module_is_present(
    monkeypatch, capsys, present
) -> None:
    if not present:
        _without_the_module(monkeypatch)
    for argv in (["--help"], ["predict", "--help"], ["all", "--help"]):
        with pytest.raises(SystemExit) as stop:
            cli.build_parser().parse_args(argv)
        assert stop.value.code == 0
        assert ("--hidden-forms" in capsys.readouterr().out) is present, argv


def test_all_passes_the_flag_to_both_package_stages(monkeypatch) -> None:
    seen: list[tuple[str, bool]] = []
    for name in ("cmd_build_index", "cmd_build_solvers", "cmd_build_fallback", "cmd_score_dev"):
        monkeypatch.setattr(cli, name, lambda args: 0)

    def package(args: argparse.Namespace) -> int:
        seen.append((args.split, cli._hidden_forms_on(args)))
        return 0

    monkeypatch.setattr(cli, "cmd_package", package)
    monkeypatch.setattr(config, "HIDDEN_FORMS", False)
    assert cli.cmd_all(cli.build_parser().parse_args(["all", "--hidden-forms"])) == 0
    assert seen == [("leaderboard", True), ("test", True)]
    seen.clear()
    assert cli.cmd_all(cli.build_parser().parse_args(["all"])) == 0
    assert seen == [("leaderboard", False), ("test", False)]


# -- byte identity -----------------------------------------------------------
@needs_solvers
@pytest.mark.parametrize("split", ["dev", "leaderboard", "test"])
def test_flag_off_regenerates_the_shipped_predictions(monkeypatch, tmp_path, split) -> None:
    monkeypatch.setattr(config, "HIDDEN_FORMS", False)
    out = tmp_path / f"{split}_predictions.jsonl"
    assert cli.main(["predict", "--split", split, "--out", str(out)]) == 0
    assert _sha256(out) == OFF_SHA256[split]
    shipped = config.ARTIFACTS / f"{split}_predictions.jsonl"
    if shipped.exists():
        assert out.read_bytes() == shipped.read_bytes()


@needs_solvers
@pytest.mark.parametrize("split", ["dev", "leaderboard"])
def test_flag_on_leaves_dev_and_leaderboard_unchanged(monkeypatch, tmp_path, split) -> None:
    monkeypatch.setattr(config, "HIDDEN_FORMS", False)
    out = tmp_path / f"{split}_predictions.jsonl"
    assert cli.main(["--hidden-forms", "predict", "--split", split, "--out", str(out)]) == 0
    assert _sha256(out) == OFF_SHA256[split]


@needs_solvers
def test_flag_on_reproduces_the_accepted_test_submission(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(config, "HIDDEN_FORMS", False)
    out = tmp_path / "test_predictions.jsonl"
    assert cli.main(["--hidden-forms", "predict", "--split", "test", "--out", str(out)]) == 0
    assert _sha256(out) == ON_TEST_SHA256
    if ACCEPTED_20261021.exists():
        assert out.read_bytes() == ACCEPTED_20261021.read_bytes()
    archive = tmp_path / "test_submission.zip"
    report = official.package(config.TEST_QUESTIONS, out, archive)
    assert report["_exit_code"] == 0, report
    assert report.get("status") == "PASS", report
    assert _sha256(archive) == ON_TEST_ZIP_SHA256


@needs_solvers
def test_flag_on_changes_only_the_unmatched_test_records(unmatched, index, router, test_split) -> None:
    solvers, fallback = build_solvers.load(), FallbackSolver.load()
    records_on, _ = predict_split(test_split, solvers, index, fallback, router)
    records_off, _ = predict_split(test_split, solvers, index, fallback)
    changed = {
        on["case_id"] for on, off in zip(records_on, records_off, strict=True) if on != off
    }
    # Every unmatched record changes (the 2 and 3 Oct build reports: 348 of 348).
    assert changed == set(unmatched)


@needs_solvers
def test_flag_on_predictions_pass_official_validation(tmp_path, index, router, test_split) -> None:
    records, _ = predict_split(
        test_split, build_solvers.load(), index, FallbackSolver.load(), router
    )
    path = write_predictions(records, tmp_path / "predictions.jsonl")
    report = official.validate(config.TEST_QUESTIONS, path)
    assert report.get("valid") is True, report
    assert report.get("errors") == [], report

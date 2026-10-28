#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Reproduce the submitted FinReason Task 3 prediction files byte for byte.

    python3 reproduce.py                    # the final entry (V1): development and test
    python3 reproduce.py --practice         # also the 332 practice cases
    python3 reproduce.py --variant V0       # an earlier variant (see REPRODUCE.md)
    python3 reproduce.py --all              # every variant below

With no arguments this rebuilds the final entry, variant V1: the development
file uploaded on 3 Oct 2026 and the test file uploaded on 3 Oct 2026, which is
the ranked Task 3 submission. Every other variant is historical and is built
only when named.

For each phase the engine (engine/run.py) runs twice on the published input
file and both runs must be byte-identical. The output must have exactly the
input ids in input order and the strict submission format, no case may raise
inside the engine, every ranked case must get a rule answer (no "unresolved"
case), the organizers' validator (scripts/validate_submission.py of the
starter kit) must print VALID, and the file's sha256 must equal the value
recorded below. Prints "VERDICT: MATCH" and exits 0 only when every check
passes; prints "VERDICT: MISMATCH" and exits 1 otherwise; exits 2 when the
inputs or the kit cannot be found.

Inputs (not included in this package): the organizers' Task 3 starter kit
(default ./kit, or --kit, or the FINREASON_TASK3_KIT environment variable)
with the ranked input files in its data/ directory. REPRODUCE.md says where
to get them. Outputs go to ./reproduced/<variant>/ (or --out). No network, no
model call, standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.dont_write_bytecode = True  # never leave __pycache__ in the kit or the package
HERE = Path(__file__).resolve().parent
# In the release package this file sits next to engine/. In the development
# tree it sits in release/, one level below engine/.
ROOT = HERE if (HERE / "engine" / "run.py").exists() else HERE.parent
ENGINE = ROOT / "engine" / "run.py"
SELFTEST = ROOT / "engine" / "selftest.py"

FINAL = "V1"

# Published sha256 of the input files. Ranked inputs: Hugging Face dataset
# YanAdjeNole/FinReason-Task3, revision f32033b1dc0c1b0ef080740ed5ee02ef6b04c931
# (2026-09-28). Practice inputs: written by the kit's
# scripts/prepare_public_dev.py from TheFinAI/FinMR revision
# 3b1babd0487c1d5a7229f7a26a1654d3fb693e92.
INPUTS = {
    "development": ("development_inputs.jsonl",
                    "592f66f6b6de3b6cbb4db16422d2fd33c6c2dc80239f090c17a6d42cac666964"),
    "test": ("test_inputs.jsonl",
             "22301f5d087a0ebea90346faa3c12f83d97ce26d77880c32d3baa32078d4db70"),
    "practice": ("public_dev_inputs.jsonl",
                 "fa3da7e55f66a62a290d630b7b80cdb2a26318f275047b23fe4cb00c707f5cde"),
}
RANKED = ("development", "test")

# name -> (engine arguments, expected sha256 per phase, what happened to it).
# The sha256 values are those of the files built on 2026-10-01/02 and, for
# the uploaded ones, of the files that were uploaded.
VARIANTS = {
    "V1": (
        ["--variant", "V1"],
        {"development": "2bebfed560c15cdead1ba707936bd608bcb59554ba41e6d526d3fdb79265aa2f",
         "test": "72c1e909bf3011256bce5a035a1d7afd5946c47e41b87375d6e4afd22f428577",
         "practice": "3582b7ff96cba3b5109af09774e35270195138409bce09f64db2b01f09675193"},
        "FINAL. Test file uploaded 2026-10-03 (the ranked submission); development file uploaded 2026-10-03",
    ),
    "V0": (
        ["--variant", "V0"],
        {"development": "575b60675ffedc7a5d5b19acbb0591b68bfb24ce9ad918a4eefe66f372f9c5c3",
         "test": "af0e1288d8daadd46afff30d953bf9c9b4ca531ab0e39b1856f87de6685f6c78",
         "practice": "3582b7ff96cba3b5109af09774e35270195138409bce09f64db2b01f09675193"},
        "historical: first development upload, 2026-10-02; its test file was replaced by V1",
    ),
    "V1M1": (
        ["--fix", "a10093", "--neg-policy", "none,last"],
        {"development": "7e531d6efd61414539c19f30e4889e35458b8aa74688ad5b8488fa5ccaf47056",
         "test": "e03ce44bfc6c699a294a6bee77678ff04edb6fd56c15b7b625220140c04b7137",
         "practice": "3fbbe189650aed796b01b073054d7da9ff3dc46affa39c75fb839d7baafda10f"},
        "historical: development probe, 2026-10-02; not adopted",
    ),
    "V1M2": (
        ["--fix", "a10093", "--neg-policy", "none,maxabs"],
        {"development": "b15419d183196a08e2b1e8adacfb06dbd5b78fadc550982e236df7ddd82e2f69",
         "test": "59d8c6351b7f0c5ffde830620bdf41737334e2295e7ffee52b73b0e2ffc56dbe",
         "practice": "26cea174e80f985b13851d8cf411a626e519c6005a4acff4503d863558d0c16a"},
        "historical: development probe, 2026-10-02; not adopted",
    ),
    "V2": (
        ["--variant", "V2"],
        {"development": "1d3a200990c553587c2569c90535430fbf6e94f79f28b0a366cfb26a65540564",
         "test": "72c1e909bf3011256bce5a035a1d7afd5946c47e41b87375d6e4afd22f428577",
         "practice": "3582b7ff96cba3b5109af09774e35270195138409bce09f64db2b01f09675193"},
        "historical: built, never uploaded",
    ),
    "M1": (
        ["--variant", "M1"],
        {"development": "8505f90c106aae0d6830a493aff28b5cade1e15ff760f58ada1f3dd1c8287a76",
         "test": "8eabb38fa004eb46006d2bad699471a7708165efdf9d4cb1e85bd52a67bbfac0",
         "practice": "3fbbe189650aed796b01b073054d7da9ff3dc46affa39c75fb839d7baafda10f"},
        "historical: built, never uploaded",
    ),
    "M2": (
        ["--variant", "M2"],
        {"development": "6e196002db82c2362069c85ad304b56312d9e10b780d27af44afd546d811c61d",
         "test": "c5ad08f0f6274c568f764603790a6f9e10d9481d0a97828d32f0878587c3c283",
         "practice": "26cea174e80f985b13851d8cf411a626e519c6005a4acff4503d863558d0c16a"},
        "historical: built, never uploaded",
    ),
    "M3": (
        ["--variant", "M3"],
        {"development": "0b95f6d73493b8b07d224551a30cbb4611d6264210f27b924eb98eb430a6b4a0",
         "test": "6224f4ecae4f625c96ca62596a4cb1b5a2f5e10014cddf89fa2fa776f27be89c",
         "practice": "c26c8df97390ac15c9d120493e384f9ecc26baed52464eca10674b27469daf35"},
        "historical: built, never uploaded",
    ),
    "V2M1": (
        ["--fix", "a10093", "--fix", "total_required", "--neg-policy", "none,last"],
        {"development": "b8fbf3c15c797ab2bdb1fd73c1d9deb861fe02ae61abe9bea11686ad2aaf2a57",
         "test": "e03ce44bfc6c699a294a6bee77678ff04edb6fd56c15b7b625220140c04b7137",
         "practice": "3fbbe189650aed796b01b073054d7da9ff3dc46affa39c75fb839d7baafda10f"},
        "historical: built, never uploaded",
    ),
    "V2M2": (
        ["--fix", "a10093", "--fix", "total_required", "--neg-policy", "none,maxabs"],
        {"development": "8631b4958135436f961b5892d03ad2859713cade008f2e101f2244efb88ffd5b",
         "test": "59d8c6351b7f0c5ffde830620bdf41737334e2295e7ffee52b73b0e2ffc56dbe",
         "practice": "26cea174e80f985b13851d8cf411a626e519c6005a4acff4503d863558d0c16a"},
        "historical: built, never uploaded",
    ),
}
ENGINE_TIMEOUT = 1800


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Failed(Exception):
    pass


def _env() -> dict:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def run_engine(inp: Path, out: Path, trace, args) -> None:
    cmd = [sys.executable, "-B", str(ENGINE), "--input", str(inp), "--output", str(out)] + list(args)
    if trace is not None:
        cmd += ["--trace", str(trace)]
    done = subprocess.run(cmd, capture_output=True, text=True, timeout=ENGINE_TIMEOUT, env=_env())
    if done.returncode != 0:
        raise Failed(f"engine exit {done.returncode} on {inp.name}: {done.stderr.strip()[-800:]}")


def _parser(kit: Path):
    """The judge's own number parser from the kit, if it can be imported."""
    try:
        sys.path.insert(0, str(kit))
        from evaluation.parser import normalize_number  # type: ignore
        return normalize_number
    except Exception:
        return None
    finally:
        if sys.path and sys.path[0] == str(kit):
            sys.path.pop(0)


def strict_format(path: Path, ids, normalize) -> None:
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf") or b"\r" in data or not data.endswith(b"\n"):
        raise Failed(f"{path.name}: BOM, CR or no trailing newline")
    rows = [json.loads(line) for line in data.decode("utf-8").splitlines()]
    if [r.get("id") for r in rows] != ids:
        raise Failed(f"{path.name}: ids differ from the input ids or their order")
    for r in rows:
        if set(r) != {"id", "extracted_value", "calculated_value"}:
            raise Failed(f"{path.name}: keys {sorted(r)}")
        for key in ("extracted_value", "calculated_value"):
            v = r[key]
            if not isinstance(v, str) or not v or "e" in v.lower() or v == "-0":
                raise Failed(f"{path.name}: value {v!r}")
            try:
                if not Decimal(v).is_finite():
                    raise InvalidOperation
            except InvalidOperation:
                raise Failed(f"{path.name}: value {v!r} is not a finite decimal")
            if normalize is not None:
                d = normalize(v)
                if d is None or not d.is_finite():
                    raise Failed(f"{path.name}: the judge's parser cannot read {v!r}")


def validate(kit: Path, pred: Path, inp: Path) -> str:
    script = kit / "scripts" / "validate_submission.py"
    done = subprocess.run([sys.executable, "-B", str(script), "--predictions", str(pred), "--reference", str(inp)],
                          cwd=str(kit), capture_output=True, text=True, timeout=600, env=_env())
    text = (done.stdout + done.stderr).strip()
    last = text.splitlines()[-1] if text else ""
    if done.returncode != 0 or "VALID" not in last or "INVALID" in last:
        raise Failed(f"organizers' validator on {pred.name}: exit {done.returncode}, {last!r}")
    return last


def build(name: str, phases, data_dir: Path, kit: Path, out_root: Path, use_validator: bool, normalize) -> dict:
    args, expected, status = VARIANTS[name]
    vdir = out_root / name
    rec = {"variant": name, "engine_args": args, "status": status, "phases": {}}
    for phase in phases:
        fname, _ = INPUTS[phase]
        inp = data_dir / fname
        ids, seen = [], set()
        with open(inp, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    cid = json.loads(line)["id"]
                    if cid not in seen:
                        seen.add(cid)
                        ids.append(cid)
        if phase == "practice":
            pred, trace = vdir / "practice_predictions.jsonl", vdir / "practice_trace.jsonl"
        else:
            pred, trace = vdir / phase / "predictions.jsonl", vdir / f"{phase}_trace.jsonl"
        pred.parent.mkdir(parents=True, exist_ok=True)
        again = vdir / f".{phase}_second_run.jsonl"
        run_engine(inp, pred, trace, args)
        run_engine(inp, again, None, args)
        identical = again.read_bytes() == pred.read_bytes()
        again.unlink()
        if not identical:
            raise Failed(f"{name} {phase}: two engine runs differ")
        strict_format(pred, ids, normalize)
        mech = Counter(json.loads(line)["mechanism"] for line in open(trace, encoding="utf-8"))
        tiers = Counter(json.loads(line)["tier"] for line in open(trace, encoding="utf-8"))
        if mech["error"]:
            raise Failed(f"{name} {phase}: {mech['error']} case(s) raised inside the engine")
        if phase in RANKED and (mech["unresolved"] or mech["unparsed"]):
            raise Failed(f"{name} {phase}: cases without a rule answer {dict(mech)}")
        got = sha256(pred)
        entry = {
            "file": str(pred.relative_to(out_root)),
            "rows": len(ids),
            "sha256": got,
            "expected_sha256": expected[phase],
            "match": got == expected[phase],
            "deterministic": True,
            "mechanisms": dict(sorted(mech.items())),
            "tiers": {str(k): v for k, v in sorted(tiers.items())},
            "fallback_E_minus_E_cases": mech["fallback"],
        }
        if use_validator:
            entry["validator"] = validate(kit, pred, inp)
        rec["phases"][phase] = entry
        flag = "OK     " if entry["match"] else "DIFFERS"
        print(f"{flag} {name:5} {phase:11} {got}  ({len(ids)} rows; mechanisms {dict(sorted(mech.items()))};"
              f" (E,-E) fallback {mech['fallback']})")
        if not entry["match"]:
            print(f"        expected {expected[phase]}")
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    pick = ap.add_mutually_exclusive_group()
    pick.add_argument("--variant", action="append", choices=sorted(VARIANTS),
                      help=f"build this variant instead of the final one ({FINAL}); repeatable")
    pick.add_argument("--all", action="store_true", help="build every variant")
    ap.add_argument("--practice", action="store_true", help="also run the 332 practice cases")
    ap.add_argument("--kit", type=Path, default=None,
                    help="the organizers' Task 3 starter kit (default: $FINREASON_TASK3_KIT or ./kit)")
    ap.add_argument("--data-dir", type=Path, default=None, help="input files (default: <kit>/data)")
    ap.add_argument("--out", type=Path, default=ROOT / "reproduced", help="output directory (default: ./reproduced)")
    ap.add_argument("--no-validator", action="store_true",
                    help="skip the organizers' validator (the sha256 check still runs)")
    ap.add_argument("--list", action="store_true", help="list the variants and exit")
    args = ap.parse_args(argv)

    if args.list:
        for name, (eargs, exp, status) in VARIANTS.items():
            print(f"{name:5} {' '.join(eargs):48} {status}")
        return 0

    names = sorted(VARIANTS, key=lambda n: (n != FINAL, n)) if args.all else (args.variant or [FINAL])
    phases = list(RANKED) + (["practice"] if args.practice else [])
    kit = (args.kit or Path(os.environ.get("FINREASON_TASK3_KIT", "") or (ROOT / "kit"))).resolve()
    data_dir = (args.data_dir or (kit / "data")).resolve()
    out_root = args.out.resolve()
    for guarded in [ROOT / "out", ROOT / "engine", kit] + sorted(ROOT.glob("accepted_*")):
        g = guarded.resolve()
        if out_root == g or g in out_root.parents:
            print(f"refusing to write into {guarded}", file=sys.stderr)
            return 2

    problems = []
    for phase in phases:
        fname, want = INPUTS[phase]
        path = data_dir / fname
        if not path.is_file():
            problems.append(f"missing input {path}")
        elif sha256(path) != want:
            problems.append(f"{path} has sha256 {sha256(path)}, expected the published {want}")
    use_validator = not args.no_validator
    if use_validator and not (kit / "scripts" / "validate_submission.py").is_file():
        problems.append(f"no organizers' validator at {kit / 'scripts' / 'validate_submission.py'}"
                        " (point --kit at the starter kit, or pass --no-validator)")
    if problems:
        for p in problems:
            print("SETUP:", p, file=sys.stderr)
        return 2

    print(f"engine: {ENGINE.parent}")
    print(f"inputs: {data_dir}")
    print(f"output: {out_root}")
    print(f"variants: {', '.join(names)} ({'final' if names == [FINAL] else 'as asked'}); phases: {', '.join(phases)}")
    started = time.time()
    report = {"final_variant": FINAL, "python": sys.version.split()[0], "variants": {}, "checks": []}
    try:
        done = subprocess.run([sys.executable, "-B", str(SELFTEST)], capture_output=True, text=True,
                              timeout=ENGINE_TIMEOUT, env=_env())
        last = done.stdout.strip().splitlines()[-1] if done.stdout.strip() else ""
        if done.returncode != 0:
            raise Failed(f"engine self-test failed: {last}")
        print(f"self-test: {last}")
        report["selftest"] = last
        normalize = _parser(kit)
        report["judge_parser_check"] = normalize is not None
        out_root.mkdir(parents=True, exist_ok=True)
        for name in names:
            report["variants"][name] = build(name, phases, data_dir, kit, out_root, use_validator, normalize)
    except Failed as exc:
        print(f"FAILED: {exc}")
        print("VERDICT: MISMATCH")
        return 1
    report["seconds"] = round(time.time() - started, 1)
    ok = all(e["match"] for v in report["variants"].values() for e in v["phases"].values())
    report["verdict"] = "MATCH" if ok else "MISMATCH"
    (out_root / "reproduce_report.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    if ok and names == [FINAL]:
        final = report["variants"][FINAL]["phases"]
        print(f"VERDICT: MATCH (final entry {FINAL}: test {final['test']['sha256'][:8]}..., "
              f"development {final['development']['sha256'][:8]}...; report {out_root / 'reproduce_report.json'})")
    elif ok:
        print(f"VERDICT: MATCH ({', '.join(names)}; report {out_root / 'reproduce_report.json'})")
    else:
        print("VERDICT: MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

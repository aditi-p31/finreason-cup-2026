"""Build a candidate test submission from the accepted archive plus final forms.

    .venv/bin/python hidden/build_candidate.py \
        [--forms-dir hidden/forms/final] [--exclude H003,H017] [--out artifacts_hidden_v1]

Base: accepted_20260914/test_predictions.jsonl (read only).  Only hidden cases
whose template has a form in --forms-dir (and is not excluded) are replaced, and
only when that form is status OK on all three draws.  In a replaced record the
final answer comes from the form, each slot comes from the form when the form
filled it legally and otherwise keeps the base value, and the record is
re-serialised exactly as ``predict.write_predictions`` writes it.  Every other
record is copied byte for byte.

Then the organisers' own ``task1_cli.py validate`` and ``package`` run (the
same CLI and arguments as ``finreason_solver.official``, with a timeout), and
the script asserts: the 580 seen records are byte-identical to the base, every
untouched hidden record is byte-identical, and accepted_20260914/test_submission.zip
still hashes to the accepted sha256.  A JSON report lands in --out.

Nothing is uploaded or submitted.  No model call, no network.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True  # keep forms/ and hidden/ free of __pycache__
HERE = Path(__file__).resolve().parent
SOLUTION = HERE.parent
for p in (str(HERE), str(SOLUTION / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

import run_forms  # noqa: E402
from finreason_solver import config, official  # noqa: E402

ACCEPTED = SOLUTION / "accepted_20260914"
BASE = ACCEPTED / "test_predictions.jsonl"
ACCEPTED_ZIP = ACCEPTED / "test_submission.zip"
ACCEPTED_ZIP_SHA256 = "42111f7f1d139b86904036bcfc43ef3ed1be2f5b0281ab4e761bcd101bdea221"
WRITABLE_ROOTS = (HERE.resolve(), (SOLUTION / "artifacts_hidden_v1").resolve(), (SOLUTION / "artifacts_hidden_v2").resolve(),
                  (SOLUTION / "artifacts_hidden_v3").resolve(), (SOLUTION / "artifacts_hidden_v4").resolve())
FORBIDDEN_ROOTS = tuple((SOLUTION / d).resolve() for d in ("artifacts", "accepted_20260914", "accepted_20260907", "src"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(record: dict[str, Any]) -> str:
    # predict.write_predictions
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def run_cli(*args: str, timeout: float) -> dict[str, Any]:
    """official.run_cli with a timeout: the organisers' CLI, same interpreter."""

    cli = official.CLI
    if not cli.exists():
        raise FileNotFoundError(f"organiser CLI not found at {cli}")
    try:
        done = subprocess.run([sys.executable, str(cli), *args], capture_output=True,
                              text=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"_exit_code": None, "_error": f"timeout after {timeout}s"}
    stdout = done.stdout.strip()
    try:
        payload = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError:
        payload = {"raw_stdout": stdout, "stderr": done.stderr}
    payload["_exit_code"] = done.returncode
    return payload


def check_out_dir(out: Path) -> Path:
    out = out.resolve()
    for bad in FORBIDDEN_ROOTS:
        if out == bad or bad in out.parents:
            raise SystemExit(f"refusing to write into {out}: inside {bad}")
    if not any(out == ok or ok in out.parents for ok in WRITABLE_ROOTS):
        raise SystemExit(f"refusing to write into {out}: outside {', '.join(map(str, WRITABLE_ROOTS))}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--forms-dir", default=str(HERE / "forms" / "final"))
    ap.add_argument("--exclude", default="", help="comma-separated keys to leave on the fallback")
    ap.add_argument("--out", default=str(SOLUTION / "artifacts_hidden_v1"))
    ap.add_argument("--timeout", type=float, default=20.0, help="seconds per form case")
    ap.add_argument("--cli-timeout", type=float, default=900.0, help="seconds per organiser CLI call")
    args = ap.parse_args(argv)

    out = check_out_dir(Path(args.out))
    out.mkdir(parents=True, exist_ok=True)
    forms_dir = Path(args.forms_dir).resolve()
    exclude = sorted({k.strip() for k in args.exclude.split(",") if k.strip()})

    zip_sha_before = sha256(ACCEPTED_ZIP)
    assert zip_sha_before == ACCEPTED_ZIP_SHA256, "accepted archive does not match its recorded sha256"
    base_sha = sha256(BASE)

    tj = json.loads(run_forms.TEMPLATES_JSON.read_text())
    templates = {t["key"]: t for t in tj["templates"]}
    hidden_to_key = {cid: t["key"] for t in tj["templates"] for cid in t["case_ids"]}
    questions = {}
    for line in config.TEST_QUESTIONS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            q = json.loads(line)
            questions[q["case_id"]] = q

    raw = BASE.read_text(encoding="utf-8")
    assert raw.endswith("\n")
    base_lines = raw[:-1].split("\n")
    base_by_id: dict[str, str] = {}
    for line in base_lines:
        rec = json.loads(line)
        assert canonical(rec) == line, "base record is not in canonical serialisation"
        base_by_id[rec["case_id"]] = line
    assert len(base_by_id) == len(base_lines) == 928
    seen_ids = sorted(set(base_by_id) - set(hidden_to_key))
    assert len(seen_ids) == 580 and seen_ids == tj["seen_case_ids"]
    assert set(hidden_to_key) <= set(base_by_id) and len(hidden_to_key) == 348

    # ---- run the final forms
    present = run_forms.discover(forms_dir) if forms_dir.exists() else []
    unknown = sorted(k for k in present if k not in templates)
    to_run = [k for k in present if k in templates and k not in exclude]
    runs = run_forms.run("final", to_run, forms_dir, args.timeout) if to_run else {"templates": {}, "summary": {}}
    included, rejected = [], {}
    override: dict[str, dict[str, Any]] = {}
    for key in to_run:
        r = runs["templates"][key]
        if r.get("status") != "OK":
            errs = [e for c in r.get("cases", []) for e in c["errors"]] + r.get("lint_errors", [])
            if r.get("load_error"):
                errs.append(r["load_error"])
            rejected[key] = errs[:6]
            continue
        included.append(key)
        for c in r["cases"]:
            override[c["case_id"]] = c

    # ---- assemble
    out_lines = []
    changed_hidden = []
    slots_from_form = 0
    for line in base_lines:
        cid = json.loads(line)["case_id"]
        if cid not in override:
            out_lines.append(line)
            continue
        assert cid in hidden_to_key, f"{cid} is not a hidden case"
        rec = json.loads(line)
        form_case = override[cid]
        rec["final_answer"] = {"value": form_case["final"]}
        base_steps = {s["slot_id"]: s["value"] for s in rec.get("steps") or []}
        steps = []
        for slot in questions[cid]["trace_spec"]["slots"]:
            sid = slot["slot_id"]
            val = form_case["slots"].get(sid)
            if val is not None:
                slots_from_form += 1
            else:
                val = base_steps.get(sid)
            if val is None:
                continue
            steps.append({"slot_id": sid, "value": val})
        rec["steps"] = steps
        new = canonical(rec)
        out_lines.append(new)
        if new != line:
            changed_hidden.append(cid)

    pred_path = out / "test_predictions.jsonl"
    pred_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")

    # ---- no-regression assertions
    cand_by_id = {json.loads(l)["case_id"]: l for l in pred_path.read_text(encoding="utf-8").splitlines()}
    assert [json.loads(l)["case_id"] for l in out_lines] == [json.loads(l)["case_id"] for l in base_lines]
    seen_identical = sum(1 for c in seen_ids if cand_by_id[c] == base_by_id[c])
    assert seen_identical == 580, f"seen records changed: {580 - seen_identical}"
    untouched_hidden = [c for c in hidden_to_key if c not in override]
    assert all(cand_by_id[c] == base_by_id[c] for c in untouched_hidden)

    # ---- organisers' validate + package
    zip_path = out / "test_submission.zip"
    if zip_path.exists():
        zip_path.unlink()  # the organiser packager refuses to overwrite
    val = run_cli("validate", "--questions", str(config.TEST_QUESTIONS),
                  "--predictions", str(pred_path), timeout=args.cli_timeout)
    pkg = run_cli("package", "--questions", str(config.TEST_QUESTIONS),
                  "--predictions", str(pred_path), "--output", str(zip_path), timeout=args.cli_timeout)

    zip_sha_after = sha256(ACCEPTED_ZIP)
    assert zip_sha_after == ACCEPTED_ZIP_SHA256, "ACCEPTED ARCHIVE CHANGED"
    assert sha256(BASE) == base_sha, "base predictions changed"

    report = {
        "base": str(BASE),
        "base_sha256": base_sha,
        "forms_dir": str(forms_dir),
        "forms_present": present,
        "unknown_form_files": unknown,
        "included_keys": sorted(included),
        "excluded_keys": exclude,
        "rejected_keys": rejected,
        "templates_on_fallback": sorted(k for k in templates if k not in included),
        "hidden_cases_replaced": len(override),
        "hidden_records_changed": len(changed_hidden),
        "slots_from_forms": slots_from_form,
        "seen_records_identical": seen_identical,
        "seen_records_total": len(seen_ids),
        "records": len(out_lines),
        "predictions_path": str(pred_path),
        "predictions_sha256": sha256(pred_path),
        "predictions_identical_to_base": sha256(pred_path) == base_sha,
        "validate": val,
        "package": pkg,
        "validate_ok": val.get("_exit_code") == 0 and val.get("valid") is True and not val.get("errors"),
        "package_ok": pkg.get("_exit_code") == 0 and pkg.get("status") == "PASS",
        "zip_path": str(zip_path),
        "zip_sha256": sha256(zip_path) if zip_path.exists() else None,
        "accepted_zip_sha256_before": zip_sha_before,
        "accepted_zip_sha256_after": zip_sha_after,
        "accepted_zip_unchanged": zip_sha_before == zip_sha_after == ACCEPTED_ZIP_SHA256,
        "form_runs": runs.get("templates", {}),
    }
    (out / "build_report.json").write_text(json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    brief = {k: report[k] for k in ("included_keys", "excluded_keys", "rejected_keys", "hidden_cases_replaced",
                                     "hidden_records_changed", "slots_from_forms", "seen_records_identical",
                                     "predictions_identical_to_base", "validate_ok", "package_ok",
                                     "zip_sha256", "accepted_zip_unchanged")}
    print(json.dumps(brief, indent=1))
    print("wrote", out / "build_report.json")
    return 0 if (report["validate_ok"] and report["package_ok"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())

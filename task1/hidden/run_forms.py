"""Run hidden-stratum transcription forms on all three draws of each template.

    .venv/bin/python hidden/run_forms.py --reader pilot --keys all --out hidden/runs/pilot.json
    .venv/bin/python hidden/run_forms.py --reader r1 --keys H003,H007 --out hidden/runs/r1_b1.json

``--reader NAME`` selects the forms directory ``hidden/forms/NAME/`` (override
with ``--forms-dir``) and is recorded in the run file.  ``--keys all`` runs every
form present in that directory.

For every case it records the final string and every slot string, serialised
with EXACTLY the shipped solver's path (``numbers.render_for_spec``, the same
``fraction_to_decimal`` half-up / ``render_exact`` branch as
``derive.evaluate_solver``) and screened with the shipped ``predict._legal_value``.

Checks: extraction success on all three draws, enum label in allowed_values,
every trace slot filled, contract-legal serialisation, a static lint of the form
source (no float literals, no float(), no file / network / process access, no
hard-coded case ids), and plausibility flags.  A bad form never aborts the run:
its errors are recorded and the next form runs.

No model call, no network, no gold.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import re
import signal
import sys
import traceback
from fractions import Fraction
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True  # keep forms/ and hidden/ free of __pycache__
HERE = Path(__file__).resolve().parent
SOLUTION = HERE.parent
for p in (str(HERE), str(SOLUTION / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

import hlib  # noqa: E402
from finreason_solver.numbers import fraction_to_decimal, question_body, render_for_spec  # noqa: E402
from finreason_solver.predict import _legal_value  # noqa: E402

TEMPLATES_JSON = HERE / "templates.json"
FORMS_ROOT = HERE / "forms"
KEY_RE = re.compile(r"^H\d{3}$")
CASE_ID_RE = re.compile(r"t1_[a-z0-9]{12,}")

FORBIDDEN_MODULES = {
    "os", "subprocess", "socket", "urllib", "http", "requests", "httpx", "aiohttp",
    "anthropic", "openai", "shutil", "pathlib", "io", "pickle", "json", "importlib",
    "builtins", "ctypes", "multiprocessing", "threading", "random", "time", "datetime",
    "sys", "glob", "tempfile", "sqlite3", "asyncio", "signal", "inspect", "gc",
}
FORBIDDEN_CALLS = {"float", "open", "eval", "exec", "compile", "__import__", "input"}
ALLOWED_MATH = {"floor", "ceil", "isqrt", "gcd", "lcm", "comb", "perm", "factorial", "prod"}

NONNEG_WORDS = (
    "probability", "factor", "retained", "retention", "multiple", "price", "cost",
    "capacity", "quantity", "count", "number of", "shares", "volume", "premium", "fee",
    "weight", "notional", "principal", "outlay", "proceeds", "minimum", "maximum",
    "required", "budget", "reserve", "cap ", "capped", "floor", "absolute",
)
NONNEG_UNITS = {"count", "tons_co2e", "usd_per_ton_co2e"}
RATIO_UNITS = {"ratio", "multiple", "dimensionless"}


class FormTimeout(Exception):
    pass


def load_templates() -> dict[str, dict[str, Any]]:
    payload = json.loads(TEMPLATES_JSON.read_text())
    return {t["key"]: t for t in payload["templates"]}


# --------------------------------------------------------------------- lint
def lint_source(source: str) -> tuple[list[str], list[str]]:
    """Static checks on a form.  Returns (errors, warnings)."""

    errors: list[str] = []
    warnings: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"syntax error: {exc}"], warnings
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, float) or isinstance(node.value, complex):
                errors.append(f"line {node.lineno}: float literal {node.value!r} (use F('...') or Fraction)")
            if isinstance(node.value, str) and CASE_ID_RE.search(node.value):
                errors.append(f"line {node.lineno}: hard-coded case id")
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for name in names:
                if name.split(".")[0] in FORBIDDEN_MODULES:
                    errors.append(f"line {node.lineno}: forbidden import {name}")
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in FORBIDDEN_CALLS:
                errors.append(f"line {node.lineno}: forbidden call {fn.id}()")
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "math" and node.attr not in ALLOWED_MATH:
                errors.append(f"line {node.lineno}: math.{node.attr} is not exact (use hlib)")
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            r = node.right
            if not (isinstance(r, ast.Constant) and isinstance(r.value, int)) and not (
                isinstance(r, ast.UnaryOp) and isinstance(r.operand, ast.Constant) and isinstance(r.operand.value, int)
            ):
                warnings.append(f"line {node.lineno}: '**' with a non-literal exponent; prefer ipow() so a non-integer exponent fails loudly")
    if not any(isinstance(n, ast.FunctionDef) and n.name == "solve" for n in tree.body):
        errors.append("no top-level def solve(b)")
    return errors, warnings


# ------------------------------------------------------------ serialisation
def serialise(value: Any, spec: dict[str, Any]) -> str:
    """Final / slot string exactly as the shipped solver writes it."""

    if spec.get("type") == "enum":
        if not isinstance(value, str):
            raise TypeError(f"enum value must be a str label, got {type(value).__name__}")
        if value not in (spec.get("allowed_values") or []):
            raise ValueError(f"enum label {value!r} not in allowed_values {spec.get('allowed_values')}")
        return value
    if isinstance(value, bool) or not isinstance(value, (int, Fraction)):
        raise TypeError(f"numeric value must be int or Fraction, got {type(value).__name__}")
    text = render_for_spec(Fraction(value), spec)
    if not _legal_value(text, spec):
        raise ValueError(f"serialised value {text!r} is not contract-legal")
    return text


def show(value: Any) -> Any:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Fraction):
        return format(fraction_to_decimal(value, 10), "f")
    if isinstance(value, (list, tuple)):
        return [show(v) for v in value]
    return repr(value)


def plausibility(value: Fraction, spec: dict[str, Any], wording: str) -> list[str]:
    flags = []
    unit = spec.get("unit")
    low = wording.lower()
    if value < 0:
        hits = [w.strip() for w in NONNEG_WORDS if w in low]
        if unit in NONNEG_UNITS:
            hits.append(f"unit={unit}")
        if hits:
            flags.append("negative_where_nonneg_implied(" + ",".join(sorted(set(hits))[:4]) + ")")
    if unit == "percent" and abs(value) > 1000:
        flags.append("percent_magnitude_over_1000")
    if unit in RATIO_UNITS and abs(value) > 100:
        flags.append(f"{unit}_magnitude_over_100")
    if "probability" in low and unit in RATIO_UNITS and not (0 <= value <= 1):
        flags.append("probability_outside_0_1")
    if value == 0:
        flags.append("exact_zero")
    return flags


def final_wording(body: str) -> str:
    """The asking sentences of a body (for the non-negativity lexicon)."""

    sents = re.split(r"(?<=[.?])\s+", body)
    asks = [s for s in sents if re.search(r"\b(Determine|Compute|Report|What|Return|Find|Solve|Calculate)\b", s)]
    return " ".join(asks[-2:]) if asks else body


# -------------------------------------------------------------------- engine
def _alarm(signum, frame):  # noqa: ARG001
    raise FormTimeout("form exceeded its time limit")


def load_form(path: Path, tag: str):
    spec = importlib.util.spec_from_file_location(tag, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_case(solve, body: str, template: dict[str, Any], timeout: float) -> dict[str, Any]:
    case: dict[str, Any] = {"final": None, "slots": {s["slot_id"]: None for s in template["slots"]},
                            "errors": [], "flags": [], "info": {}}
    hlib.NONRATIONAL_USED.clear()
    old = signal.signal(signal.SIGALRM, _alarm)
    signal.setitimer(signal.ITIMER_REAL, timeout)
    try:
        out = solve(body)
    except FormTimeout as exc:
        case["errors"].append(f"timeout: {exc}")
        return case
    except BaseException as exc:  # noqa: BLE001
        if isinstance(exc, KeyboardInterrupt):
            raise
        tb = traceback.extract_tb(exc.__traceback__)
        where = next((f"{Path(f.filename).name}:{f.lineno}" for f in reversed(tb) if "forms" in f.filename), "")
        case["errors"].append(f"{type(exc).__name__}: {exc} {where}".strip())
        return case
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
    for op in sorted(set(hlib.NONRATIONAL_USED)):
        case["flags"].append(f"non_rational:{op}")

    if not isinstance(out, dict) or "final" not in out:
        case["errors"].append("solve() must return a dict with a 'final' key")
        return case
    unknown = set(out) - {"final", "slots", "info"}
    if unknown:
        case["errors"].append(f"unknown result keys {sorted(unknown)}")
    answer_spec = template["answer_spec"]
    body_ask = final_wording(body)
    try:
        case["final"] = serialise(out["final"], answer_spec)
        if answer_spec.get("type") != "enum":
            case["flags"] += ["final:" + f for f in plausibility(Fraction(out["final"]), answer_spec, body_ask)]
    except Exception as exc:  # noqa: BLE001
        case["errors"].append(f"final: {type(exc).__name__}: {exc}")

    slots_out = out.get("slots") or {}
    if not isinstance(slots_out, dict):
        case["errors"].append("'slots' must be a dict {slot_id: value}")
        slots_out = {}
    by_id = {s["slot_id"]: s for s in template["slots"]}
    for sid, val in slots_out.items():
        if sid not in by_id:
            case["errors"].append(f"slot {sid!r} is not a slot of this template")
            continue
        spec = by_id[sid]["result_spec"]
        try:
            case["slots"][sid] = serialise(val, spec)
            if spec.get("type") != "enum":
                case["flags"] += [f"slot:{sid}:" + f for f in plausibility(Fraction(val), spec, by_id[sid]["description"])]
        except Exception as exc:  # noqa: BLE001
            case["errors"].append(f"slot {sid}: {type(exc).__name__}: {exc}")
    info = out.get("info") or {}
    if isinstance(info, dict):
        case["info"] = {str(k): show(v) for k, v in info.items()}
    return case


def run_template(key: str, form_path: Path, template: dict[str, Any], *, reader: str,
                 timeout: float = 20.0) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "key": key, "type": template["type"], "form": str(form_path), "form_sha256": None,
        "lint_errors": [], "lint_warnings": [], "load_error": None, "cases": [],
    }
    solve = None
    try:
        source = form_path.read_text()
        rec["form_sha256"] = hashlib.sha256(source.encode()).hexdigest()
        rec["lint_errors"], rec["lint_warnings"] = lint_source(source)
        if rec["lint_errors"]:
            # a form that fails the static lint is never executed
            raise RuntimeError("not executed: fix the lint errors first")
        old = signal.signal(signal.SIGALRM, _alarm)
        signal.setitimer(signal.ITIMER_REAL, timeout)
        try:
            module = load_form(form_path, f"hform_{re.sub(r'[^A-Za-z0-9_]', '_', reader)}_{key}")
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old)
        if getattr(module, "KEY", None) != key:
            rec["lint_errors"].append(f"form declares KEY={getattr(module, 'KEY', None)!r}, file is {key}")
        solve = getattr(module, "solve", None)
        if not callable(solve):
            solve = None
            raise AttributeError("form has no callable solve(b)")
    except BaseException as exc:  # noqa: BLE001
        if isinstance(exc, KeyboardInterrupt):
            raise
        rec["load_error"] = f"{type(exc).__name__}: {exc}"
        solve = None
    for cid, qtext in zip(template["case_ids"], template["questions"]):
        if solve is None:
            case = {"final": None, "slots": {s["slot_id"]: None for s in template["slots"]},
                    "errors": ["form not run: " + (rec["load_error"] or "did not load")], "flags": [], "info": {}}
        else:
            case = run_case(solve, question_body(qtext), template, timeout)
        rec["cases"].append({"case_id": cid, **case})
    finals = [c["final"] for c in rec["cases"]]
    rec["extraction_ok"] = all(not c["errors"] for c in rec["cases"]) and rec["load_error"] is None
    rec["finals_ok"] = all(f is not None for f in finals)
    unfilled = sorted({sid for c in rec["cases"] for sid, v in c["slots"].items() if v is None})
    rec["slots_unfilled"] = unfilled
    rec["slots_complete"] = not unfilled
    rec["flags"] = sorted({f for c in rec["cases"] for f in c["flags"]})
    if template["type"] == "enum" and rec["finals_ok"] and len(set(finals)) == 1:
        rec["flags"].append("enum_constant_across_draws")
    rec["status"] = "OK" if (rec["extraction_ok"] and rec["finals_ok"] and not rec["lint_errors"]) else "FAIL"
    return rec


def discover(forms_dir: Path) -> list[str]:
    return sorted(p.stem for p in forms_dir.glob("H[0-9][0-9][0-9].py"))


def run(reader: str, keys: list[str] | str, forms_dir: Path, timeout: float = 20.0) -> dict[str, Any]:
    templates = load_templates()
    present = discover(forms_dir) if forms_dir.exists() else []
    wanted = present if keys == "all" else list(keys)
    results: dict[str, Any] = {}
    missing = []
    for key in wanted:
        if not KEY_RE.match(key) or key not in templates:
            results[key] = {"key": key, "status": "FAIL", "load_error": "unknown template key", "cases": []}
            continue
        path = forms_dir / f"{key}.py"
        if not path.exists():
            missing.append(key)
            continue
        results[key] = run_template(key, path, templates[key], reader=reader, timeout=timeout)
    ok = [k for k, r in results.items() if r.get("status") == "OK"]
    summary = {
        "templates_run": len(results),
        "ok": len(ok),
        "fail": sorted(k for k, r in results.items() if r.get("status") != "OK"),
        "no_form": sorted(missing),
        "slots_incomplete": sorted(k for k, r in results.items() if r.get("status") == "OK" and not r.get("slots_complete")),
        "flagged": sorted(k for k, r in results.items() if r.get("flags")),
        "cases_ok": sum(1 for r in results.values() for c in r.get("cases", []) if not c["errors"] and c["final"] is not None),
        "slots_filled": sum(1 for r in results.values() for c in r.get("cases", []) for v in c["slots"].values() if v is not None),
        "slots_total": sum(len(c["slots"]) for r in results.values() for c in r.get("cases", [])),
    }
    return {"reader": reader, "forms_dir": str(forms_dir),
            "templates_json_sha256": hashlib.sha256(TEMPLATES_JSON.read_bytes()).hexdigest(),
            "summary": summary, "templates": results}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reader", required=True, help="reader name; forms are read from hidden/forms/<reader>/")
    ap.add_argument("--keys", default="all",
                    help="comma-separated template keys, 'all' (every form present), or 'batch:N'")
    ap.add_argument("--out", required=True, help="run file to write (JSON)")
    ap.add_argument("--forms-dir", default=None, help="override hidden/forms/<reader>/")
    ap.add_argument("--timeout", type=float, default=20.0, help="seconds per case")
    args = ap.parse_args(argv)
    forms_dir = Path(args.forms_dir) if args.forms_dir else FORMS_ROOT / args.reader
    spec = args.keys.strip()
    if spec == "all":
        keys: list[str] | str = "all"
    elif spec.startswith("batch:"):
        batches = json.loads(TEMPLATES_JSON.read_text())["batches"]
        keys = list(batches[spec.split(":", 1)[1].strip()])
    else:
        keys = [k.strip() for k in spec.split(",") if k.strip()]
    payload = run(args.reader, keys, forms_dir, args.timeout)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    for key, r in sorted(payload["templates"].items()):
        errs = ([r["load_error"]] if r.get("load_error") else []) + r.get("lint_errors", [])
        errs += [e for c in r.get("cases", []) for e in c["errors"]]
        errs = list(dict.fromkeys(errs))
        finals = [c["final"] for c in r.get("cases", [])]
        print(f"{key} {r.get('status'):<4} finals={finals} unfilled={r.get('slots_unfilled', [])} "
              f"flags={r.get('flags', [])}" + (f" ERRORS={errs[:3]}" if errs else ""))
    print(json.dumps(payload["summary"], indent=1))
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

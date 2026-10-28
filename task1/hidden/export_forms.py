"""Copy the reviewed hidden-stratum forms into the solver package.

    .venv/bin/python hidden/export_forms.py           # refresh the package copy
    .venv/bin/python hidden/export_forms.py --check   # write nothing; exit 1 if stale

Copies ``hidden/forms/final/HNNN.py`` and ``hidden/hlib.py`` byte for byte to
``src/finreason_solver/hiddenforms/forms/HNNN.py`` and
``src/finreason_solver/hiddenforms/hlib.py``, and writes
``src/finreason_solver/hiddenforms/routes.json``: for every template key, the
boolean-masked shape its test questions share (``build_templates.bshape``, the
rule that formed the templates) and the sha256 of its form, plus the sha256 of
the helper.  The router computes the same shape from a question's text at run
time and refuses any form or helper whose bytes do not match these pins.

The forms are copied, never edited: ``hidden/forms/final/`` stays the source
of truth.  Reads ``hidden/templates.json``; no model call, no network.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
SOLUTION = HERE.parent
for p in (str(HERE), str(SOLUTION / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from build_templates import bshape  # noqa: E402

FINAL = HERE / "forms" / "final"
HELPER = HERE / "hlib.py"
TEMPLATES_JSON = HERE / "templates.json"
PACKAGE = SOLUTION / "src" / "finreason_solver" / "hiddenforms"
RULE = ("numbers.mask_numbers(question), then every literal true/false (any case) "
        "replaced by <B>, whitespace runs collapsed to one space, stripped")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def plan() -> dict[Path, bytes]:
    """Every file the package copy should hold, with its exact bytes."""

    tj = json.loads(TEMPLATES_JSON.read_text(encoding="utf-8"))
    templates = {t["key"]: t for t in tj["templates"]}
    keys = sorted(p.stem for p in FINAL.glob("H[0-9][0-9][0-9].py"))
    if keys != sorted(templates):
        missing = sorted(set(templates) - set(keys))
        extra = sorted(set(keys) - set(templates))
        raise SystemExit(f"forms/final does not cover templates.json: missing {missing}, extra {extra}")

    files: dict[Path, bytes] = {}
    helper = HELPER.read_bytes()
    files[PACKAGE / "hlib.py"] = helper
    forms: dict[str, dict[str, str]] = {}
    seen_shapes: dict[str, str] = {}
    for key in keys:
        data = (FINAL / f"{key}.py").read_bytes()
        files[PACKAGE / "forms" / f"{key}.py"] = data
        shapes = {bshape(q) for q in templates[key]["questions"]}
        if len(shapes) != 1:
            raise SystemExit(f"{key}: its questions do not share one shape")
        shape = shapes.pop()
        if shape in seen_shapes:
            raise SystemExit(f"{key} and {seen_shapes[shape]} share a shape")
        seen_shapes[shape] = key
        forms[key] = {"type": templates[key]["type"], "sha256": sha256(data), "shape": shape}
    routes = {
        "about": "route table for finreason_solver.hiddenforms, written by hidden/export_forms.py",
        "source": "hidden/forms/final (forms), hidden/hlib.py (helper), hidden/templates.json (shapes)",
        "rule": RULE,
        "templates_json_sha256": sha256(TEMPLATES_JSON.read_bytes()),
        "helper": {"file": "hlib.py", "sha256": sha256(helper)},
        "forms": forms,
    }
    files[PACKAGE / "routes.json"] = (json.dumps(routes, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode()
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="write nothing; exit 1 if the package copy is stale")
    args = ap.parse_args(argv)

    files = plan()
    wanted_forms = {p.name for p in files if p.parent == PACKAGE / "forms"}
    present_forms = {p.name for p in (PACKAGE / "forms").glob("*.py")} if (PACKAGE / "forms").exists() else set()
    stale = sorted(present_forms - wanted_forms)
    differ = sorted(str(p.relative_to(SOLUTION)) for p, data in files.items()
                    if not p.exists() or p.read_bytes() != data)
    if args.check:
        print(json.dumps({"differ": differ, "stale_forms": stale, "up_to_date": not differ and not stale}, indent=1))
        return 0 if not differ and not stale else 1
    for path, data in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_bytes() != data:
            path.write_bytes(data)
    for name in stale:
        (PACKAGE / "forms" / name).unlink()
    print(json.dumps({"forms": len(wanted_forms), "written": differ, "removed": stale}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Compare two run_forms run files template by template.

    .venv/bin/python hidden/compare.py hidden/runs/r1_b1.json hidden/runs/r2_b1.json [--out hidden/runs/cmp_b1.json]

A template is AGREE only if both runs have it, every final string is identical
and non-null on all three cases, and every slot string is identical on all three
cases (a slot both runs left unfilled counts as identical and is listed under
``slots_unfilled_both``).  Otherwise DISAGREE, with every differing value, or
MISSING_A / MISSING_B when one run lacks the template.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def compare(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    ta, tb = a["templates"], b["templates"]
    out: dict[str, Any] = {}
    for key in sorted(set(ta) | set(tb)):
        if key not in ta:
            out[key] = {"status": "MISSING_A"}
            continue
        if key not in tb:
            out[key] = {"status": "MISSING_B"}
            continue
        ca = {c["case_id"]: c for c in ta[key].get("cases", [])}
        cb = {c["case_id"]: c for c in tb[key].get("cases", [])}
        diffs = []
        unfilled_both = set()
        for cid in sorted(set(ca) | set(cb)):
            x, y = ca.get(cid), cb.get(cid)
            if x is None or y is None:
                diffs.append({"case_id": cid, "field": "case", "a": x is not None, "b": y is not None})
                continue
            if x["final"] is None or y["final"] is None or x["final"] != y["final"]:
                diffs.append({"case_id": cid, "field": "final", "a": x["final"], "b": y["final"],
                              "a_errors": x["errors"], "b_errors": y["errors"]})
            for sid in sorted(set(x["slots"]) | set(y["slots"])):
                vx, vy = x["slots"].get(sid), y["slots"].get(sid)
                if vx != vy:
                    diffs.append({"case_id": cid, "field": f"slot:{sid}", "a": vx, "b": vy})
                elif vx is None:
                    unfilled_both.add(sid)
        out[key] = {"status": "AGREE" if not diffs else "DISAGREE", "diffs": diffs,
                    "slots_unfilled_both": sorted(unfilled_both),
                    "a_status": ta[key].get("status"), "b_status": tb[key].get("status")}
    counts: dict[str, int] = {}
    for r in out.values():
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {
        "a": {"reader": a.get("reader"), "forms_dir": a.get("forms_dir")},
        "b": {"reader": b.get("reader"), "forms_dir": b.get("forms_dir")},
        "counts": counts,
        "agree": sorted(k for k, r in out.items() if r["status"] == "AGREE"),
        "disagree": sorted(k for k, r in out.items() if r["status"] == "DISAGREE"),
        "missing": sorted(k for k, r in out.items() if r["status"].startswith("MISSING")),
        "templates": out,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_a")
    ap.add_argument("run_b")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    a = json.loads(Path(args.run_a).read_text())
    b = json.loads(Path(args.run_b).read_text())
    result = compare(a, b)
    for key, r in result["templates"].items():
        line = f"{key} {r['status']}"
        if r["status"] == "DISAGREE":
            line += " " + "; ".join(f"{d['case_id']} {d['field']}: {d.get('a')!r} vs {d.get('b')!r}" for d in r["diffs"][:4])
        print(line)
    print(json.dumps(result["counts"], sort_keys=True))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
        print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""FinReason Task 3 deterministic rule engine: CLI.

    python3 engine/run.py --input kit/data/development_inputs.jsonl --output out/development_predictions.jsonl

Reads each record's ``id`` and ``query`` only (any other field, such as a
practice-set rule label, is ignored). Writes one JSON object per input id,
in input order, with ``extracted_value`` and ``calculated_value`` as strings.
No network, no model calls.

A case whose parsing raises is still written (as "0","0", so the file keeps
every id), but the run then exits with status 2 and prints the count, so a
broken engine cannot pass silently. ``--allow-errors`` turns that off.

``--variant`` picks a row of ``engine.VARIANTS``. With no ``--variant``,
``--fix`` or ``--neg-policy`` the engine runs V1, the final entry (the Test
and Development files uploaded on 2026-10-03). Every other variant is
historical and runs only when named: ``--variant V0`` is the engine of the
first Development upload (2026-10-02). ``--fix`` and ``--neg-policy`` set the
switches one by one instead. See REPRODUCE.md, sections 3 and 4.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import engine as _engine  # noqa: E402
from engine import Prediction, predict  # noqa: E402

FINAL_VARIANT = "V1"  # the final entry: the default when no switch is given


def safe_predict(query: str) -> Prediction:
    try:
        return predict(query)
    except Exception as exc:  # never drop a line: a missing id invalidates the file
        return Prediction("0", "0", "error", type(exc).__name__, 6, "none")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--trace", default=None, help="optional JSONL with the mechanism and evidence tier per case")
    ap.add_argument("--allow-errors", action="store_true", help="exit 0 even when a case raised")
    ap.add_argument("--variant", default=None, choices=sorted(_engine.VARIANTS),
                    help="a named switch set from engine.VARIANTS (default V1, the final entry; "
                         "V0 and the others are historical)")
    ap.add_argument("--fix", action="append", default=[], choices=list(_engine.KNOWN_FIXES),
                    help="turn one fix on (repeatable); not combined with --variant")
    ap.add_argument("--neg-policy", default=None,
                    help="DQC_US_0015 choice among several tested negatives as PREFER,ORDER "
                         "(prefer: nondim|dim|none; order: first|last|maxabs|minabs; V0 is nondim,first); "
                         "not combined with --variant")
    args = ap.parse_args(argv)
    if args.variant and (args.fix or args.neg_policy):
        ap.error("--variant cannot be combined with --fix or --neg-policy")
    if args.variant:
        _engine.configure_variant(args.variant)
    elif args.fix or args.neg_policy:
        _engine.configure(args.fix, tuple(args.neg_policy.split(",")) if args.neg_policy else _engine.NEG_V0)
    else:
        _engine.configure_variant(FINAL_VARIANT)

    rows, trace, tally, tiers, seen = [], [], Counter(), Counter(), set()
    with open(args.input, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            cid = rec["id"]
            if cid in seen:
                continue
            seen.add(cid)
            p = safe_predict(rec.get("query") or "")
            tally[p.mechanism] += 1
            tiers[p.tier] += 1
            rows.append({"id": cid, "extracted_value": p.extracted_value, "calculated_value": p.calculated_value})
            trace.append({"id": cid, "mechanism": p.mechanism, "detail": p.detail, "tier": p.tier,
                          "confidence": p.confidence, "competing": p.competing})

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    if args.trace:
        with open(args.trace, "w", encoding="utf-8", newline="\n") as fh:
            for r in trace:
                fh.write(json.dumps(r) + "\n")
    print(f"wrote {len(rows)} predictions to {out}")
    for k, v in tally.most_common():
        print(f"  {k:12} {v:5}")
    print("  tiers: " + ", ".join(f"{k}:{v}" for k, v in sorted(tiers.items())))
    if tally["error"] and not args.allow_errors:
        print(f"ERROR: {tally['error']} case(s) raised inside the engine; do not use this file.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""How many practice cases any query-only system must miss.

    python3 tools/query_identifiability.py              # kit at ./kit
    python3 tools/query_identifiability.py --kit PATH

Reads the practice set with its answers (<kit>/data/public_dev.jsonl; id,
dqc_id, query, answer) and groups the cases whose whole query string is
byte-identical. A group whose cases carry different gold pairs (extracted
value, calculated value; compared as decimals after removing commas) cannot
be answered in full by any deterministic system that reads only the query:
it gives every case of the group the same pair, so at most the most frequent
gold pair of the group can match. Summed over all groups this is an upper
bound on exact pair matches for such a system, whatever its rules.

The bound concerns the supplied practice inputs and exact matching of both
numbers. It is not a bound on the development or test sets, on a system with
other inputs, or on a judge that accepts other pairs.

Expected output for the practice file of the cup release (sha256 cfdd41ae...):
332 cases, 295 distinct queries, 17 conflicting groups (32 cases DQC_US_0015,
15 cases DQC_US_0117), at most 308 of 332 exact (92.77%).
No network, no model call.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent


def gold_pair(answer: dict) -> tuple[Decimal, Decimal]:
    return tuple(Decimal(str(answer[k]).replace(",", "").strip())
                 for k in ("extracted_value", "calculated_value"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kit", type=Path, default=ROOT / "kit", help="the organizers' starter kit (default ./kit)")
    args = ap.parse_args()

    path = args.kit / "data" / "public_dev.jsonl"
    data = path.read_bytes()
    rows = [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[row["query"]].append(row)

    best = 0
    conflicting = []
    for members in groups.values():
        pairs = Counter(gold_pair(r["answer"]) for r in members)
        best += max(pairs.values())
        if len(pairs) > 1:
            conflicting.append(members)

    out = {
        "practice_file_sha256": hashlib.sha256(data).hexdigest(),
        "cases": len(rows),
        "distinct_queries": len(groups),
        "repeated_query_groups": sum(len(m) > 1 for m in groups.values()),
        "conflicting_groups": len(conflicting),
        "conflicting_cases_by_rule": dict(sorted(Counter(r["dqc_id"] for m in conflicting for r in m).items())),
        "max_exact_query_only": best,
        "max_exact_query_only_pct": f"{100 * best / len(rows):.2f}",
        "conflicting_group_ids": [sorted(r["id"] for r in m) for m in conflicting],
    }
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Deterministic DEVSET / HOLDOUT split of the 332 Task 3 practice cases.

Reads ONLY kit/data/public_dev_inputs.jsonl (id, dqc_id, query). It never opens
the gold file, so the split cannot depend on answers.

Method: within each DQC rule (stratum), order the case ids by
sha256(SALT + ":" + id) and put the first round(n * 2/3) in DEVSET, the rest
in HOLDOUT. Same inputs -> same split, on any machine.

The filer CIK (read from the instance contexts in the query text) is recorded
per case only so that cross-split filer overlap can be reported; it plays no
role in the assignment.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUTS = ROOT / "kit" / "data" / "public_dev_inputs.jsonl"
OUT = ROOT / "split.json"
SALT = "finreason-task3-split-v1"
DEV_FRACTION = 2 / 3

#: The practice set's instance documents were cut at 32,768 characters (the
#: section, header included, is 32,789 long). The ranked-phase files were
#: re-released on 2026-09-28 without this cut. Flag computed from inputs only.
TRUNC_LEN = 32_780

_CIK = re.compile(r'<identifier scheme="[^"]*">([^<]+)</identifier>')


def key(case_id: str) -> str:
    return hashlib.sha256(f"{SALT}:{case_id}".encode("utf-8")).hexdigest()


def main() -> int:
    by_rule = defaultdict(list)
    cik = {}
    trunc = {}
    with INPUTS.open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            assert "answer" not in row, "inputs file must not carry gold"
            by_rule[row["dqc_id"]].append(row["id"])
            m = _CIK.search(row["query"])
            cik[row["id"]] = m.group(1).strip() if m else None
            q = row["query"]
            a, b = q.find("##Instance document"), q.find("##US GAAP Taxonomy")
            trunc[row["id"]] = (b - a) >= TRUNC_LEN if a >= 0 and b > a else True

    devset, holdout, strata = [], [], {}
    for rule in sorted(by_rule):
        ids = sorted(by_rule[rule], key=key)
        n_dev = round(len(ids) * DEV_FRACTION)
        devset += ids[:n_dev]
        holdout += ids[n_dev:]
        strata[rule] = {"n": len(ids), "devset": n_dev, "holdout": len(ids) - n_dev}

    devset.sort()
    holdout.sort()
    dev_ciks = {cik[i] for i in devset}
    hold_ciks = {cik[i] for i in holdout}
    shared = dev_ciks & hold_ciks
    hold_in_shared = sum(1 for i in holdout if cik[i] in shared)

    out = {
        "version": "v1",
        "method": (
            "Stratified by dqc_id; within each rule, ids ordered by "
            f"sha256('{SALT}:' + id); first round(n*2/3) -> DEVSET, rest -> HOLDOUT. "
            "Built from public_dev_inputs.jsonl only (no gold read)."
        ),
        "salt": SALT,
        "source_file": "kit/data/public_dev_inputs.jsonl",
        "source_sha256": hashlib.sha256(INPUTS.read_bytes()).hexdigest(),
        "counts": {"total": len(devset) + len(holdout), "devset": len(devset), "holdout": len(holdout)},
        "strata": strata,
        "filer_overlap": {
            "distinct_filers_total": len(dev_ciks | hold_ciks),
            "distinct_filers_devset": len(dev_ciks),
            "distinct_filers_holdout": len(hold_ciks),
            "filers_in_both": len(shared),
            "holdout_cases_whose_filer_also_in_devset": hold_in_shared,
            "holdout_unseen_filer_cases": len(holdout) - hold_in_shared,
            "note": (
                "Split is by case id, not by filer, so some filers appear on both sides. "
                "The ranked phases are split by company, so HOLDOUT is optimistic for any "
                "filer-specific behaviour."
            ),
        },
        "rule": "The builder must not open HOLDOUT gold. Score HOLDOUT once, at the end.",
        "devset": devset,
        "holdout": holdout,
        # Diagnostic subset: HOLDOUT cases whose filer never appears in DEVSET.
        # Closest local proxy for the ranked phases' unseen-company condition.
        "holdout_unseen_filer": sorted(i for i in holdout if cik[i] not in shared),
        # Gold-free flag: instance section cut at 32,768 chars in the practice data.
        # On these cases the asked-for fact is often missing from the text, which
        # caps practice accuracy; the ranked files do not have this cut.
        "instance_truncated_note": (
            f"instance section length >= {TRUNC_LEN} chars (computed from inputs only)"
        ),
        "devset_untruncated": sorted(i for i in devset if not trunc[i]),
        "holdout_untruncated": sorted(i for i in holdout if not trunc[i]),
        "truncation_counts": {
            rule: {
                "truncated": sum(1 for i in by_rule[rule] if trunc[i]),
                "untruncated": sum(1 for i in by_rule[rule] if not trunc[i]),
            }
            for rule in sorted(by_rule)
        },
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("counts", "strata", "filer_overlap", "truncation_counts")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

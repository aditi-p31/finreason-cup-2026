#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""How much the practice HOLDOUT shares with the build set (DEVSET).

    python3 tools/holdout_overlap.py                       # counts only (no gold read)
    python3 tools/holdout_overlap.py --score P.jsonl       # plus the deterministic judge per subset

Reads split.json and the practice inputs (<kit>/data/public_dev_inputs.jsonl;
id, dqc_id, query). The filer of a case is the text of the instance's
<identifier> element (the CIK), the field tools/make_split.py records; every
practice case carries exactly one distinct identifier, which is checked.

Counts, for the 111 HOLDOUT cases:
  * filer shared: the case's filer also files at least one DEVSET case;
  * identical query: the whole query string is byte-identical to a DEVSET
    case's query (same filing excerpt and same question);
  * identical question: only the question (the text from the last
    "Question1:" to the end) equals a DEVSET case's question.

--score adds the organizers' deterministic judge (kit evaluation package,
via tools/score_split.py) on each subset, and the HOLDOUT cases whose query
AND expected answer equal a DEVSET case's (exact duplicates); that reads the
practice gold.
No network, no model call.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
_IDENT = re.compile(r"<(?:[\w-]+:)?identifier\b[^>]*>\s*([^<\s]+)\s*</(?:[\w-]+:)?identifier>")


def question_text(query: str) -> str:
    k = query.rfind("Question1:")
    if k < 0:
        raise SystemExit("a practice query without 'Question1:'")
    return query[k:]


def counts(split: dict, rows: dict) -> dict:
    dev, hold = list(split["devset"]), list(split["holdout"])
    filer = {}
    for cid, row in rows.items():
        found = {x.lstrip("0") for x in _IDENT.findall(row["query"])}
        if len(found) != 1:
            raise SystemExit(f"{cid}: {len(found)} distinct identifiers")
        filer[cid] = found.pop()
    dev_filers = {filer[i] for i in dev}
    hold_filers = {filer[i] for i in hold}
    dev_queries = {rows[i]["query"] for i in dev}
    dev_questions = {question_text(rows[i]["query"]) for i in dev}
    shared = [i for i in hold if filer[i] in dev_filers]
    unseen = [i for i in hold if filer[i] not in dev_filers]
    same_query = [i for i in hold if rows[i]["query"] in dev_queries]
    same_question = [i for i in hold if question_text(rows[i]["query"]) in dev_questions]
    untruncated = set(split["holdout_untruncated"])
    rule = {i: rows[i]["dqc_id"] for i in rows}

    def by_rule(ids):
        return dict(sorted(Counter(rule[i] for i in ids).items()))

    return {
        "holdout": len(hold),
        "devset": len(dev),
        "distinct_filers": {"devset": len(dev_filers), "holdout": len(hold_filers),
                            "both": len(dev_filers & hold_filers), "total": len(dev_filers | hold_filers)},
        "holdout_filer_shared_with_devset": {"n": len(shared), "by_rule": by_rule(shared)},
        "holdout_filer_not_in_devset": {"n": len(unseen), "by_rule": by_rule(unseen),
                                        "equals_split_json_list": sorted(unseen) == sorted(split["holdout_unseen_filer"])},
        "holdout_query_identical_to_a_devset_case": {
            "n": len(same_query), "by_rule": by_rule(same_query),
            "all_with_shared_filer": set(same_query) <= set(shared),
            "complete_instance": sum(i in untruncated for i in same_query)},
        "holdout_question_text_identical_to_a_devset_question": {"n": len(same_question),
                                                                 "by_rule": by_rule(same_question)},
        "_ids": {"shared": shared, "unseen": unseen, "identical_query": same_query},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kit", type=Path, default=ROOT / "kit", help="the organizers' starter kit (default ./kit)")
    ap.add_argument("--split", type=Path, default=ROOT / "split.json")
    ap.add_argument("--score", type=Path, default=None, help="practice predictions to score per subset")
    args = ap.parse_args()
    split = json.loads(args.split.read_text(encoding="utf-8"))
    rows = {}
    with open(args.kit / "data" / "public_dev_inputs.jsonl", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            rows[row["id"]] = row
    if set(rows) != set(split["devset"]) | set(split["holdout"]) or set(split["devset"]) & set(split["holdout"]):
        raise SystemExit("split.json does not partition the practice inputs")
    result = counts(split, rows)
    ids = result.pop("_ids")
    if args.score:
        os.environ["FINREASON_TASK3_KIT"] = str(args.kit.resolve())  # read by score_split
        sys.path.insert(0, str(ROOT / "tools"))
        import score_split  # noqa: E402  (imports the kit's evaluation package)

        # Exact duplicates need the answers: same query AND same expected answer
        # as some DEVSET case.
        answer = {}
        with open(args.kit / "data" / "public_dev.jsonl", encoding="utf-8") as fh:
            for line in fh:
                row = json.loads(line)
                answer[row["id"]] = json.dumps(row["answer"], sort_keys=True)
        dev_pairs = {(rows[i]["query"], answer[i]) for i in split["devset"]}
        duplicate = [i for i in ids["identical_query"] if (rows[i]["query"], answer[i]) in dev_pairs]
        result["holdout_query_and_answer_identical_to_a_devset_case"] = {"n": len(duplicate)}
        subsets = {"holdout": list(split["holdout"]), "filer_shared": ids["shared"], "filer_not_in_devset": ids["unseen"],
                   "identical_query": ids["identical_query"],
                   "not_identical_query": [i for i in split["holdout"] if i not in set(ids["identical_query"])],
                   "exact_duplicate": duplicate,
                   "without_exact_duplicates": [i for i in split["holdout"] if i not in set(duplicate)]}
        scored = {}
        for name, sub in subsets.items():
            score_split.subset_ids = lambda _n, _g, sub=sub: list(sub)
            run = score_split.score(str(args.score), "all")
            correct = sum(r.label == "A" for r in run.case_results)
            scored[name] = {"n": len(sub), "correct": correct, "ACC": run.summary.to_dict()["ACC"]}
        result["deterministic_judge"] = scored
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

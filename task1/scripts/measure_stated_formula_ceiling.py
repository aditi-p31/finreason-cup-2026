#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Measure the coverage ceiling of a stated-formula parser before building it.

Many cup questions state their own formula in the question text, with symbol
bindings declared in the same sentence ("V=550000.5", "credit impact =
V*(qc/100)*sc", "compute goodwill = total consideration minus identifiable net
assets").  A deterministic parser for that pattern is the one zero-inference
route to hidden-stratum credit.  Its ceiling is a coverage fact that exists
before any parser code does: on cases whose text states no formula, such a
parser can produce nothing, so the fraction of cases carrying at least one
explicit formula statement upper-bounds everything the route can earn.

Protocol mirrors evaluate_fallback.py's hidden_like bucket: the 174
intermediate and advanced dev cases, the only difficulties the hidden stratum
contains.  The detector reads only the target question's own text and fits
nothing from any split, so withholding the target template (the fallback's
leave-one-template-out control) changes nothing by construction.

Detection: a bare "=" (not >=, <=, ==, !=) whose right-hand clause is not a
plain numeric binding and contains an arithmetic operator, symbolic
(+ * / x ^, a spaced or identifier-flanked minus) or verbal (minus, plus,
times, divided, over).  Every matched case was hand-checked once against the
question text when this script was written.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from finreason_solver import config, dataio  # noqa: E402

NUM_BINDING = re.compile(
    r"^\s*-?\d[\d,]*(?:\.\d+)?"
    r"(?:\s*(?:percent|%|USD|usd|bps|years?|months?|days?|units?))?"
    r"\s*(?:[.,;)]|$)"
)
OP_SYMBOL = re.compile(r"[+*/×^]| x | - |\w-\w")
OP_WORD = re.compile(r"\b(minus|plus|times|divided|over)\b", re.I)
BARE_EQUALS = re.compile(r"(?<![<>!=])=(?!=)")
CLAUSE_END = re.compile(r"\.(?=\s|$)|;")


def stated_formula_clauses(question_text: str) -> list[str]:
    body = question_text.split("Answer format:")[0]
    clauses: list[str] = []
    for match in BARE_EQUALS.finditer(body):
        rhs = body[match.end() :]
        if NUM_BINDING.match(rhs):
            continue  # a value binding such as "V=550000.5 USD", not a formula
        tail = rhs[:160]
        end = CLAUSE_END.search(tail)
        clause = tail[: end.start()] if end else tail
        if OP_SYMBOL.search(clause) or OP_WORD.search(clause):
            clauses.append(clause.strip())
    return clauses


def main() -> int:
    split = dataio.load_dev()
    assert split.manifest is not None

    counters = {
        key: {"cases": 0, "with_stated_formula": 0}
        for key in ("hidden_like", "intermediate", "advanced")
    }
    matched_cases: list[str] = []

    for case_id in sorted(split.questions):
        difficulty = split.manifest[case_id]["difficulty"]
        if difficulty not in ("intermediate", "advanced"):
            continue
        hit = bool(stated_formula_clauses(split.questions[case_id]["question"]))
        for key in ("hidden_like", difficulty):
            counters[key]["cases"] += 1
            counters[key]["with_stated_formula"] += int(hit)
        if hit:
            matched_cases.append(case_id)

    report: dict[str, object] = {
        "protocol": (
            "pattern coverage over the 174 intermediate+advanced dev cases, the "
            "hidden_like bucket of fallback_loto.json; the detector reads only "
            "the target question's text, so the fallback's leave-one-template-out "
            "control is satisfied trivially (nothing is fitted)"
        ),
        "note": (
            "coverage upper-bounds the stated-formula parser: cases without an "
            "explicit formula statement yield it nothing, so this ceiling holds "
            "before any parser exists and before any parsing loss"
        ),
        "matched_case_ids": matched_cases,
    }
    for key, counts in counters.items():
        report[key] = {
            "cases": counts["cases"],
            "with_stated_formula": counts["with_stated_formula"],
            "coverage": round(counts["with_stated_formula"] / counts["cases"], 6)
            if counts["cases"]
            else None,
        }
    print(json.dumps({k: v for k, v in report.items() if k != "matched_case_ids"},
                     indent=1, sort_keys=True))
    out = config.ARTIFACTS / "stated_formula_ceiling.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

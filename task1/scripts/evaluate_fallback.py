#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Measure the unseen-template guess policy under leave-one-template-out.

The 348 hidden test cases are unseen *structures*, so the only honest estimate
of what the guess policy is worth there comes from hiding a template's own
priors and asking the model to guess it cold.  This is an optimistic bound:
a held-out seen template still shares its domain, its topic and often its exact
wording family with the training pool, which a genuinely novel hidden structure
does not.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from finreason_solver import config, dataio  # noqa: E402
from finreason_solver.fallback import FallbackSolver, fit  # noqa: E402
from finreason_solver.numbers import canonical_decimal, gold_fraction  # noqa: E402


def main() -> int:
    groups = dataio.labelled_instances()
    model = fit(groups)
    split = dataio.load_dev()
    assert split.gold is not None and split.manifest is not None

    counters: dict[str, dict[str, int]] = {
        key: dict.fromkeys(
            ("final_total", "final_emitted", "final_hits", "slot_total",
             "slot_emitted", "slot_hits"),
            0,
        )
        for key in ("all", "hidden_like")
    }

    for case_id in sorted(split.questions):
        question = split.questions[case_id]
        gold = split.gold[case_id]
        row = split.manifest[case_id]
        template_id = row["template_id"]
        guess = model.guess(question, exclude=template_id)
        # The hidden stratum contains only intermediate and advanced templates.
        buckets = ["all"] + (
            ["hidden_like"] if row["difficulty"] in ("intermediate", "advanced") else []
        )

        for key in buckets:
            counters[key]["final_total"] += 1
        if guess["final"] is not None:
            for key in buckets:
                counters[key]["final_emitted"] += 1
            spec = question["answer_spec"]
            try:
                if spec["type"] == "enum":
                    hit = guess["final"] == gold["final_value"]
                elif (spec.get("rounding") or {}).get("mode") == "exact":
                    hit = gold_fraction(guess["final"]) == gold_fraction(
                        gold["final_value"]
                    )
                else:
                    hit = canonical_decimal(guess["final"], spec) == canonical_decimal(
                        gold["final_value"], spec
                    )
            except (ValueError, ArithmeticError):
                hit = False
            for key in buckets:
                counters[key]["final_hits"] += int(hit)

        for slot in question["trace_spec"]["slots"]:
            for key in buckets:
                counters[key]["slot_total"] += 1
            produced = guess["steps"].get(slot["slot_id"])
            if produced is None:
                continue
            for key in buckets:
                counters[key]["slot_emitted"] += 1
            spec = slot["result_spec"]
            expected = gold["slot_values"][slot["slot_id"]]
            try:
                if spec["type"] == "enum":
                    hit = produced == expected
                elif (spec.get("rounding") or {}).get("mode") == "exact":
                    hit = gold_fraction(produced) == gold_fraction(expected)
                else:
                    hit = canonical_decimal(produced, spec) == canonical_decimal(
                        expected, spec
                    )
            except (ValueError, ArithmeticError):
                hit = False
            for key in buckets:
                counters[key]["slot_hits"] += int(hit)

    report: dict[str, object] = {
        "protocol": "leave-one-template-out over the 290 dev cases",
        "note": (
            "hidden_like restricts to intermediate+advanced templates, the only "
            "difficulties present in the hidden stratum"
        ),
    }
    for key, counts in counters.items():
        report[key] = {
            "final_answer": {
                "cases": counts["final_total"],
                "guessed": counts["final_emitted"],
                "correct": counts["final_hits"],
                "accuracy": round(counts["final_hits"] / counts["final_total"], 6)
                if counts["final_total"]
                else None,
            },
            "slots": {
                "slots": counts["slot_total"],
                "guessed": counts["slot_emitted"],
                "correct": counts["slot_hits"],
                "accuracy": round(counts["slot_hits"] / counts["slot_total"], 6)
                if counts["slot_total"]
                else None,
            },
        }
    print(json.dumps(report, indent=1, sort_keys=True))
    out = config.ARTIFACTS / "fallback_loto.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

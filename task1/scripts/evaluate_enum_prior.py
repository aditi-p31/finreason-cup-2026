#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Leave-one-out accuracy of the per-template enum majority prior.

Used only where the induction search could not derive a rule for an enum
output.  A wrong label scores the same as ``null`` under the cup scorer, so the
prior is free; this script says what it is actually worth.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from finreason_solver import config, dataio  # noqa: E402


def _leave_one_out(labels: list[str]) -> int:
    hits = 0
    for index, held_out in enumerate(labels):
        rest = labels[:index] + labels[index + 1 :]
        counts = Counter(rest)
        predicted = min(counts, key=lambda label: (-counts[label], label))
        hits += int(predicted == held_out)
    return hits


def main() -> int:
    groups = dataio.labelled_instances()
    final_hits = final_total = 0
    slot_hits = slot_total = 0
    templates = 0
    for instances in groups.values():
        first = instances[0]
        touched = False
        if first.answer_spec.get("type") == "enum":
            labels = [instance.final_text or "" for instance in instances]
            final_hits += _leave_one_out(labels)
            final_total += len(labels)
            touched = True
        for position, slot in enumerate(first.question["trace_spec"]["slots"]):
            if slot["result_spec"].get("type") != "enum":
                continue
            labels = [instance.slot_texts[position] for instance in instances]
            slot_hits += _leave_one_out(labels)
            slot_total += len(labels)
            touched = True
        templates += int(touched)

    report = {
        "protocol": "leave-one-instance-out within each template (11 folds)",
        "templates_with_enum_outputs": templates,
        "final_answer": {
            "cases": final_total,
            "correct": final_hits,
            "accuracy": round(final_hits / final_total, 6) if final_total else None,
        },
        "slots": {
            "slots": slot_total,
            "correct": slot_hits,
            "accuracy": round(slot_hits / slot_total, 6) if slot_total else None,
        },
    }
    print(json.dumps(report, indent=1, sort_keys=True))
    out = config.ARTIFACTS / "enum_prior_loo.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

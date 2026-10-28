#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""What the rational-aware number tokeniser buys, measured.

The naive ``-?\\d[\\d,]*\\.?\\d*`` tokeniser splits the rationals the cup embeds
in some questions (``-3/17`` becomes two numbers), which both destabilises the
per-template parameter count and fragments the shape index.
"""

from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from finreason_solver import config, dataio  # noqa: E402
from finreason_solver.numbers import question_body  # noqa: E402

NAIVE = re.compile(r"-?\d[\d,]*\.?\d*")
RATIONAL_AWARE = re.compile(r"-?\d+(?:,\d+)*(?:\.\d+)?(?:/\d+(?:,\d+)*(?:\.\d+)?)?")
WHITESPACE = re.compile(r"\s+")


def measure(pattern: re.Pattern[str]) -> dict[str, object]:
    groups = dataio.labelled_instances()
    unstable = [
        template_id
        for template_id, instances in groups.items()
        if len(
            {
                len(pattern.findall(question_body(instance.question["question"])))
                for instance in instances
            }
        )
        > 1
    ]
    index: dict[str, set[str]] = {}
    for template_id, instances in groups.items():
        for instance in instances:
            key = WHITESPACE.sub(
                " ", pattern.sub("<N>", question_body(instance.question["question"]))
            ).strip()
            index.setdefault(key, set()).add(template_id)
    conflicts = sum(1 for values in index.values() if len(values) > 1)
    lookup = {key: next(iter(v)) for key, v in index.items() if len(v) == 1}

    coverage = {}
    for name, split in (
        ("leaderboard_580", dataio.load_leaderboard()),
        ("test_928", dataio.load_test()),
    ):
        hits = sum(
            1
            for question in split.questions.values()
            if WHITESPACE.sub(
                " ", pattern.sub("<N>", question_body(question["question"]))
            ).strip()
            in lookup
        )
        coverage[name] = {"exact_shape_hits": hits, "cases": len(split.questions)}
    return {
        "templates_with_unstable_parameter_count": len(unstable),
        "distinct_shape_keys": len(index),
        "shape_keys_mapping_to_more_than_one_template": conflicts,
        "exact_shape_coverage": coverage,
    }


def main() -> int:
    report = {
        "naive_tokeniser": measure(NAIVE),
        "rational_aware_tokeniser": measure(RATIONAL_AWARE),
    }
    print(json.dumps(report, indent=1, sort_keys=True))
    out = config.ARTIFACTS / "tokeniser_ablation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

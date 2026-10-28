#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Reproduce the organisers' published B0/B1 practice-set scores locally.

This is the calibration check for the whole harness: if running the cup's own
baseline generator through the cup's own scorer gives back the numbers printed
on the leaderboard page, then our dev score is measuring the same quantity the
leaderboard measures.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from finreason_solver import config, official  # noqa: E402

PUBLISHED = {
    "b0": {"final_answer": "0.000000", "reasoning_steps": "0.000000"},
    "b1": {"final_answer": "0.020833", "reasoning_steps": "0.011574"},
    "b2": {"final_answer": "0.285873", "reasoning_steps": "0.592606"},
}


def main() -> int:
    results = {}
    with tempfile.TemporaryDirectory() as tmp:
        for name in ("b0", "b1"):
            path = Path(tmp) / f"{name}.jsonl"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(official.CLI),
                    f"baseline-{name}",
                    "--questions",
                    str(config.DEV_QUESTIONS),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            path.write_text(completed.stdout)
            report = official.score_dev(path)
            results[name] = {
                "seen_fac": report["scores"]["seen_fac"],
                "seen_checkpoint": report["scores"]["seen_checkpoint"],
                "published_final_answer": PUBLISHED[name]["final_answer"],
                "published_reasoning_steps": PUBLISHED[name]["reasoning_steps"],
                "matches_published": (
                    round(float(report["scores"]["seen_fac"]), 6)
                    == float(PUBLISHED[name]["final_answer"])
                    and round(float(report["scores"]["seen_checkpoint"]), 6)
                    == float(PUBLISHED[name]["reasoning_steps"])
                ),
            }
    results["b2"] = {
        "note": "Fin-o1-8B; published only, not reproducible without the model",
        "published_final_answer": PUBLISHED["b2"]["final_answer"],
        "published_reasoning_steps": PUBLISHED["b2"]["reasoning_steps"],
    }
    print(json.dumps(results, indent=1, sort_keys=True))
    (config.ARTIFACTS / "baselines.json").write_text(
        json.dumps(results, indent=1, sort_keys=True)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

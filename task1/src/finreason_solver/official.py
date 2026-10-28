# SPDX-License-Identifier: Apache-2.0
"""Thin wrapper around the organisers' own participant kit.

We never reimplement scoring, validation or packaging: every number in the
report comes from ``IEEE-bigdata-cup/scripts/task1_cli.py`` run as a
subprocess, so it is the organisers' code that produces it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import config

CLI = config.CUP_REPO / "scripts" / "task1_cli.py"


def run_cli(*args: str) -> tuple[int, dict[str, Any]]:
    if not CLI.exists():
        raise FileNotFoundError(f"organiser CLI not found at {CLI}")
    completed = subprocess.run(
        [sys.executable, str(CLI), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = completed.stdout.strip()
    try:
        payload = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError:
        payload = {"raw_stdout": stdout, "stderr": completed.stderr}
    return completed.returncode, payload


def score_dev(predictions: Path) -> dict[str, Any]:
    code, payload = run_cli(
        "score-dev",
        "--questions", str(config.DEV_QUESTIONS),
        "--gold", str(config.DEV_GOLD),
        "--manifest", str(config.DEV_MANIFEST),
        "--predictions", str(predictions),
    )
    payload["_exit_code"] = code
    return payload


def validate(questions: Path, predictions: Path) -> dict[str, Any]:
    code, payload = run_cli(
        "validate", "--questions", str(questions), "--predictions", str(predictions)
    )
    payload["_exit_code"] = code
    return payload


def package(questions: Path, predictions: Path, output: Path) -> dict[str, Any]:
    code, payload = run_cli(
        "package",
        "--questions", str(questions),
        "--predictions", str(predictions),
        "--output", str(output),
    )
    payload["_exit_code"] = code
    return payload


def leaderboard_admit(
    questions: Path, expected_ids: Path, submission_zip: Path
) -> dict[str, Any]:
    code, payload = run_cli(
        "leaderboard-admit",
        "--questions", str(questions),
        "--expected-ids", str(expected_ids),
        "--submission-zip", str(submission_zip),
    )
    payload["_exit_code"] = code
    return payload

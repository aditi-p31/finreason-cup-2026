# SPDX-License-Identifier: Apache-2.0
"""``all`` and ``run.sh`` must exit non-zero when any stage fails.

Every stage is replaced by a stub, so nothing here builds, predicts, scores or
writes outside pytest's temporary directory.
"""

from __future__ import annotations

import argparse
import os
import stat
import subprocess
from pathlib import Path

import pytest

from finreason_solver import build_solvers, cli, config, official

ROOT = Path(__file__).resolve().parents[1]
STAGES = (
    "cmd_build_index",
    "cmd_build_solvers",
    "cmd_build_fallback",
    "cmd_score_dev",
    "cmd_package",
)


def _stub_stages(monkeypatch, codes: dict[str, int]) -> list[str]:
    calls: list[str] = []
    for name in STAGES:
        def stage(args, name=name):
            label = name if name != "cmd_package" else f"cmd_package:{args.split}"
            calls.append(label)
            return codes.get(label, codes.get(name, 0))

        monkeypatch.setattr(cli, name, stage)
    return calls


def _all_args() -> argparse.Namespace:
    return cli.build_parser().parse_args(["all"])


def test_all_returns_zero_and_runs_every_stage_in_order(monkeypatch) -> None:
    calls = _stub_stages(monkeypatch, {})
    assert cli.cmd_all(_all_args()) == 0
    assert calls == [
        "cmd_build_index",
        "cmd_build_solvers",
        "cmd_build_fallback",
        "cmd_score_dev",
        "cmd_package:leaderboard",
        "cmd_package:test",
    ]


@pytest.mark.parametrize(
    "failing, code",
    [
        ("cmd_build_index", 1),
        ("cmd_build_solvers", 1),
        ("cmd_build_fallback", 1),
        ("cmd_score_dev", 2),
        ("cmd_package:leaderboard", 2),
        ("cmd_package:test", 2),
    ],
)
def test_all_stops_at_the_first_failing_stage(monkeypatch, capsys, failing, code) -> None:
    calls = _stub_stages(monkeypatch, {failing: code})
    assert cli.cmd_all(_all_args()) == code
    assert calls[-1] == failing
    assert failing.split(":")[0].replace("cmd_", "").replace("_", "-") in capsys.readouterr().err


def test_main_propagates_a_failing_stage(monkeypatch) -> None:
    _stub_stages(monkeypatch, {"cmd_score_dev": 2})
    assert cli.main(["all"]) == 2


def test_build_solvers_fails_when_a_template_errored(monkeypatch, tmp_path) -> None:
    payloads = [
        {"template_id": "t.ok", "contract_test": {"final_perfect": True, "slots_perfect": True}},
        {"template_id": "t.bad", "error": "RuntimeError: boom"},
    ]
    monkeypatch.setattr(config, "ARTIFACTS", tmp_path)
    monkeypatch.setattr(build_solvers, "build_two_stage", lambda **_: payloads)
    monkeypatch.setattr(build_solvers, "save", lambda items: tmp_path / "solvers.json")
    args = cli.build_parser().parse_args(["build-solvers"])
    assert cli.cmd_build_solvers(args) == 1
    payloads.pop()
    assert cli.cmd_build_solvers(args) == 0


@pytest.mark.parametrize(
    "package_code, admit_code, expected",
    [(0, 0, 0), (1, 0, 2), (0, 1, 2)],
)
def test_package_fails_on_a_failed_package_or_admission(
    monkeypatch, tmp_path, package_code, admit_code, expected
) -> None:
    monkeypatch.setattr(config, "ARTIFACTS", tmp_path)
    monkeypatch.setattr(cli, "_predict", lambda *a, **k: {"cases": 0})
    monkeypatch.setattr(official, "package", lambda *a: {"_exit_code": package_code})
    monkeypatch.setattr(official, "leaderboard_admit", lambda *a: {"_exit_code": admit_code})
    args = argparse.Namespace(split="leaderboard", no_fallback=False)
    assert cli.cmd_package(args) == expected
    if admit_code == 0:
        test_args = argparse.Namespace(split="test", no_fallback=False)
        assert cli.cmd_package(test_args) == expected


@pytest.mark.parametrize("code", [0, 3])
def test_run_sh_exits_with_the_pipeline_status(tmp_path, code) -> None:
    fake = tmp_path / "fake-python"
    fake.write_text(f"#!/bin/sh\nexit {code}\n")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    env = dict(os.environ, PY=str(fake))
    completed = subprocess.run(
        ["bash", str(ROOT / "run.sh")], env=env, capture_output=True, timeout=60
    )
    assert completed.returncode == code

# SPDX-License-Identifier: Apache-2.0
"""The ship gate: no solver leaves the build unless it reproduces its gold."""

from __future__ import annotations

import json

import pytest

from finreason_solver import build_solvers, config
from finreason_solver.dataio import labelled_instances
from finreason_solver.derive import TemplateSolver, contract_test, evaluate_solver

pytestmark = pytest.mark.skipif(
    not config.SOLVERS_JSON.exists(),
    reason="run `python -m finreason_solver build-solvers` first",
)


@pytest.fixture(scope="module")
def payloads() -> list[dict]:
    return json.loads(config.SOLVERS_JSON.read_text())


@pytest.fixture(scope="module")
def groups() -> dict:
    return labelled_instances()


def test_no_solver_errors(payloads: list[dict]) -> None:
    assert [item["template_id"] for item in payloads if item.get("error")] == []


def test_every_shipped_solver_replays_all_eleven_gold_instances(
    payloads: list[dict], groups: dict
) -> None:
    """Re-derive nothing; just replay what shipped, against gold, from disk."""

    shipped = [item for item in payloads if build_solvers.is_shippable(item)]
    assert shipped, "no solver passed the gate"
    failures = []
    for payload in shipped:
        solver = TemplateSolver.from_json(payload)
        report = contract_test(solver, groups[payload["template_id"]])
        if not (report["final_perfect"] and report["slots_perfect"]):
            failures.append((payload["template_id"], report))
    assert failures == []


def test_shipped_solvers_are_deterministic(
    payloads: list[dict], groups: dict
) -> None:
    shipped = [item for item in payloads if build_solvers.is_shippable(item)][:40]
    for payload in shipped:
        solver = TemplateSolver.from_json(payload)
        instance = groups[payload["template_id"]][0]
        first = evaluate_solver(solver, instance.params)
        second = evaluate_solver(solver, instance.params)
        assert first == second


def test_solver_parameter_arity_matches_its_template(
    payloads: list[dict], groups: dict
) -> None:
    for payload in payloads:
        if payload.get("error"):
            continue
        instances = groups[payload["template_id"]]
        assert payload["n_params"] == len(instances[0].params)

# SPDX-License-Identifier: Apache-2.0
"""Predictions must be admissible to the organisers' own validator."""

from __future__ import annotations

import pytest

from finreason_solver import build_solvers, config, dataio, official
from finreason_solver.fallback import FallbackSolver
from finreason_solver.predict import predict_split, write_predictions
from finreason_solver.shapes import ShapeIndex

pytestmark = pytest.mark.skipif(
    not config.SOLVERS_JSON.exists(),
    reason="run `python -m finreason_solver build-solvers` first",
)


@pytest.fixture(scope="module")
def pieces():
    return ShapeIndex.build(), build_solvers.load(), FallbackSolver.load()


@pytest.mark.parametrize(
    "loader,questions,count",
    [
        (dataio.load_dev, config.DEV_QUESTIONS, 290),
        (dataio.load_leaderboard, config.LB_QUESTIONS, 580),
        (dataio.load_test, config.TEST_QUESTIONS, 928),
    ],
)
def test_predictions_pass_official_validation(
    tmp_path, pieces, loader, questions, count
) -> None:
    index, solvers, fallback = pieces
    records, _ = predict_split(loader(), solvers, index, fallback)
    assert len(records) == count
    path = write_predictions(records, tmp_path / "predictions.jsonl")
    report = official.validate(questions, path)
    assert report.get("valid") is True, report
    assert report.get("errors") == [], report
    assert report.get("record_count") == count


def test_records_carry_exactly_the_five_contract_fields(pieces) -> None:
    index, solvers, fallback = pieces
    records, _ = predict_split(dataio.load_dev(), solvers, index, fallback)
    for record in records:
        assert set(record) == {
            "schema_version",
            "dataset_version",
            "case_id",
            "final_answer",
            "steps",
        }
        assert record["schema_version"] == "finreason.task1.prediction/1.0.0"
        assert record["dataset_version"] == "task1-v4"


def test_no_unknown_slot_ids_are_emitted(pieces) -> None:
    """An unknown slot_id invalidates the whole submission, not just the case."""

    index, solvers, fallback = pieces
    split = dataio.load_dev()
    records, _ = predict_split(split, solvers, index, fallback)
    for record in records:
        expected = {
            slot["slot_id"]
            for slot in split.questions[record["case_id"]]["trace_spec"]["slots"]
        }
        emitted = {step["slot_id"] for step in record["steps"]}
        assert emitted <= expected
        assert len(emitted) == len(record["steps"])

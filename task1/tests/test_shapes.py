# SPDX-License-Identifier: Apache-2.0
"""Template identification must be exact where it claims to be exact."""

from __future__ import annotations

import collections

from finreason_solver import dataio
from finreason_solver.shapes import ShapeIndex, shape_key


def test_index_has_no_shape_collisions() -> None:
    index = ShapeIndex.build()
    assert index.conflicts == {}


def test_dev_290_recovers_every_manifest_template() -> None:
    index = ShapeIndex.build()
    split = dataio.load_dev()
    wrong = [
        case_id
        for case_id, question in split.questions.items()
        if index.identify(question["question"]).template_id
        != split.manifest[case_id]["template_id"]
    ]
    assert wrong == []


def test_train_2900_recovers_every_manifest_template() -> None:
    index = ShapeIndex.build()
    split = dataio.load_train()
    wrong = [
        case_id
        for case_id, question in split.questions.items()
        if index.identify(question["question"]).template_id
        != split.manifest[case_id]["template_id"]
    ]
    assert wrong == []


def test_leaderboard_is_fully_matched() -> None:
    index = ShapeIndex.build()
    split = dataio.load_leaderboard()
    matches = index.identify_many(split.questions.values())
    assert len(matches) == 580
    assert all(match.template_id for match in matches.values())


def test_test_split_separates_seen_from_hidden_at_the_official_counts() -> None:
    """580 seen + 348 hidden is frozen in finreason_task1.scoring."""

    index = ShapeIndex.build()
    split = dataio.load_test()
    matches = index.identify_many(split.questions.values())
    matched = sum(1 for match in matches.values() if match.template_id)
    assert len(matches) == 928
    assert matched == 580
    assert len(matches) - matched == 348


def test_parameter_counts_are_stable_within_a_template() -> None:
    for template_id, instances in dataio.labelled_instances().items():
        counts = {len(instance.params) for instance in instances}
        assert len(counts) == 1, (template_id, counts)

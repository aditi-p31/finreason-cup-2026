# SPDX-License-Identifier: Apache-2.0
"""Our understanding of the cup contract, checked against the cup's own code."""

from __future__ import annotations

import json
from decimal import Decimal
from fractions import Fraction

import pytest

from finreason_solver import config
from finreason_solver.dataio import load_dev, to_instance
from finreason_solver.numbers import canonical_decimal, render_exact, render_for_spec
from finreason_task1 import scoring
from finreason_task1.contracts import validate_submission


def _dev():
    return load_dev()


def test_null_and_wrong_answers_score_identically() -> None:
    """The basis of the never-abstain policy: both are worth exactly zero."""

    split = _dev()
    case_id = sorted(split.questions)[0]
    question = split.questions[case_id]
    gold = split.gold[case_id]
    base = {
        "schema_version": config.PREDICTION_SCHEMA_VERSION,
        "dataset_version": question["dataset_version"],
        "case_id": case_id,
        "steps": [],
    }
    null_score = scoring.score_case(question, gold, {**base, "final_answer": None})
    wrong_score = scoring.score_case(
        question, gold, {**base, "final_answer": {"value": "-987654321.99"}}
    )
    assert null_score.fac == 0
    assert wrong_score.fac == 0


def test_missing_slot_is_not_penalised_beyond_being_unmatched() -> None:
    split = _dev()
    case_id = next(
        cid
        for cid in sorted(split.questions)
        if split.questions[cid]["trace_spec"]["slots"]
    )
    question = split.questions[case_id]
    gold = split.gold[case_id]
    base = {
        "schema_version": config.PREDICTION_SCHEMA_VERSION,
        "dataset_version": question["dataset_version"],
        "case_id": case_id,
        "final_answer": None,
    }
    empty = scoring.score_case(question, gold, {**base, "steps": []})
    assert empty.matched_slots == 0
    assert empty.total_slots == len(question["trace_spec"]["slots"])


def test_our_canonical_decimal_matches_the_scorer() -> None:
    spec = {"type": "decimal", "rounding": {"mode": "half_up", "decimal_places": 2}}
    for text in ("0.005", "-0.005", "1.005", "2.675", "-0.001", "1e2"):
        assert canonical_decimal(text, spec) == scoring._canonical_decimal(text, spec)


def test_every_gold_slot_value_round_trips_through_our_serialiser() -> None:
    """Whatever the cup writes as gold, we must be able to write too."""

    split = _dev()
    checked = 0
    for case_id, question in split.questions.items():
        instance = to_instance(question, split.gold[case_id], None)
        for position, spec in enumerate(instance.slot_specs):
            if spec["type"] != "decimal":
                continue
            value = instance.slot_fraction(position)
            rendered = render_for_spec(value, spec)
            assert scoring.value_matches(
                rendered, instance.slot_texts[position], spec
            )
            checked += 1
    assert checked > 400


def test_targets_file_scores_one_under_the_official_scorer() -> None:
    """Sanity check that the organiser scorer is wired up correctly."""

    from finreason_solver import official

    report = official.score_dev(config.DEV_DATA / "dev_targets.jsonl")
    assert report["_exit_code"] == 0
    assert report["scores"]["seen_fac"] == "1"
    assert report["scores"]["seen_checkpoint"] == "1"


# ------------------------------------------- non-terminating decimal handling


def _corpus_values():
    """(value_text, spec) for every numeric gold value we have labels for."""

    from finreason_solver.dataio import load_train

    for split in (load_train(), _dev()):
        for case_id, question in split.questions.items():
            instance = to_instance(question, split.gold[case_id], None)
            for position, spec in enumerate(instance.slot_specs):
                yield instance.slot_texts[position], spec
            yield instance.final_text, question["answer_spec"]


def test_every_gold_value_in_the_corpus_round_trips_under_their_own_validator() -> None:
    """9.6% of gold slots are repeating rationals; a systematic mismatch there
    would cost checkpoint credit silently, so this checks all 3,190 cases, not
    just dev, against the organisers' own `_validate_decimal_text` (the rule
    that splits finite decimals from irreducible rationals) and their own
    `value_matches`.
    """

    from fractions import Fraction

    from finreason_solver.numbers import gold_fraction, is_terminating
    from finreason_task1.contracts import _validate_decimal_text

    seen = {"exact_terminating": 0, "exact_repeating": 0, "half_up": 0}
    for text, spec in _corpus_values():
        if spec["type"] != "enum":
            value = gold_fraction(text)
            rendered = render_for_spec(value, spec)
            assert _validate_decimal_text(rendered, spec) is None, (text, rendered)
            assert scoring.value_matches(rendered, text, spec), (text, rendered)
            if spec["rounding"]["mode"] == "exact":
                if is_terminating(value):
                    seen["exact_terminating"] += 1
                else:
                    seen["exact_repeating"] += 1
                    # Round-trip: our rational parses back to the same value.
                    assert gold_fraction(rendered) == value
            else:
                seen["half_up"] += 1
    assert seen["exact_repeating"] > 500, seen
    assert seen["exact_terminating"] > 4_000, seen
    assert seen["half_up"] > 3_000, seen


def test_the_wrong_notation_for_a_repeating_value_is_rejected_or_wrong() -> None:
    """Both halves of the exact-value rule are load-bearing, in both directions.

    A terminating value written as ``a/b`` is a *validation* error (it rejects
    the whole submission); a repeating value written as a truncated decimal
    validates fine and silently scores zero.  Neither may be accidentally OK.
    """

    from finreason_solver.numbers import (
        fraction_to_decimal,
        gold_fraction,
        is_terminating,
    )
    from finreason_task1.contracts import _validate_decimal_text

    exact = {"type": "decimal", "rounding": {"mode": "exact"}, "unit": "usd"}
    terminating = gold_fraction("2.5")
    as_rational = f"{terminating.numerator}/{terminating.denominator}"
    assert _validate_decimal_text(as_rational, exact) is not None

    repeating = gold_fraction("200/3")
    assert not is_terminating(repeating)
    truncated = format(fraction_to_decimal(repeating, 12), "f")
    assert _validate_decimal_text(truncated, exact) is None  # validates...
    assert not scoring.value_matches(truncated, "200/3", exact)  # ...and is wrong


def test_gold_re_serialised_by_us_scores_one_through_the_organisers_cli() -> None:
    """The end-to-end proof: gold -> our Fraction -> our serialiser -> their CLI.

    Also runs the mutation arm, which renders every repeating value as a
    12-place decimal instead.  That arm still *validates*, so the loss it
    causes would never announce itself; it is measured here so the size of
    what the canonicalisation is buying is on the record.
    """

    import json
    import tempfile
    from pathlib import Path

    from finreason_solver import official
    from finreason_solver.numbers import (
        fraction_to_decimal,
        gold_fraction,
        is_terminating,
    )
    from finreason_solver.predict import write_predictions

    split = _dev()

    def build(mutate: bool):
        records, repeating = [], 0
        for case_id in sorted(split.questions):
            question = split.questions[case_id]
            instance = to_instance(question, split.gold[case_id], None)
            steps = []
            for position, slot in enumerate(question["trace_spec"]["slots"]):
                spec = slot["result_spec"]
                text = instance.slot_texts[position]
                if spec["type"] == "enum":
                    value = text
                else:
                    value_fraction = gold_fraction(text)
                    if not is_terminating(value_fraction):
                        repeating += 1
                        if mutate:
                            value = format(
                                fraction_to_decimal(value_fraction, 12), "f"
                            )
                            steps.append({"slot_id": slot["slot_id"], "value": value})
                            continue
                    value = render_for_spec(value_fraction, spec)
                steps.append({"slot_id": slot["slot_id"], "value": value})
            answer_spec = question["answer_spec"]
            final_text = instance.final_text
            final_value = (
                final_text
                if answer_spec["type"] == "enum"
                else render_for_spec(gold_fraction(final_text), answer_spec)
            )
            records.append(
                {
                    "schema_version": config.PREDICTION_SCHEMA_VERSION,
                    "dataset_version": question["dataset_version"],
                    "case_id": case_id,
                    "final_answer": {"value": final_value},
                    "steps": steps,
                }
            )
        return records, repeating

    with tempfile.TemporaryDirectory() as directory:
        clean_path = Path(directory) / "clean.jsonl"
        records, repeating = build(mutate=False)
        assert repeating > 0
        write_predictions(records, clean_path)
        clean = official.score_dev(clean_path)
        assert clean["_exit_code"] == 0
        assert clean["scores"]["seen_fac"] == "1"
        assert clean["scores"]["seen_checkpoint"] == "1"
        assert clean["counts"]["matched_slots"] == clean["counts"]["total_slots"]

        mutated_path = Path(directory) / "mutated.jsonl"
        write_predictions(build(mutate=True)[0], mutated_path)
        mutated = official.score_dev(mutated_path)
        # Still a legal submission -- the loss is silent, which is the hazard.
        assert mutated["_exit_code"] == 0
        assert (
            mutated["counts"]["matched_slots"]
            == clean["counts"]["matched_slots"] - repeating
        )
        assert mutated["scores"]["seen_checkpoint"] != "1"


@pytest.mark.skipif(
    not config.SOLVERS_JSON.exists() or not config.SHAPE_INDEX_JSON.exists(),
    reason="run `python -m finreason_solver all` first (needs solvers.json and shape_index.json)",
)
def test_our_emitted_dev_predictions_are_canonical_under_the_organisers_scorer() -> None:
    """The values ``predict.py`` actually emits, not a re-serialisation of gold.

    ``evaluate_solver`` picks exact-vs-half-up from the *solver's* slot kind,
    not from the question's spec, so the serialiser tests above do not by
    themselves prove the emitted file is canonical.  This one checks the real
    output of the shipped solvers on dev: every emitted value passes the
    organisers' ``_validate_decimal_text`` for its own spec, and every emitted
    value that is exactly right (as a Fraction, after the spec's rounding) is
    accepted by the organisers' ``value_matches``.  That isolates
    canonicalisation from solver accuracy: a wrong value is excused, a right
    value that fails to match is not.  The repeating-rational branch must be
    exercised, and the organisers' CLI must count exactly the matches we count.
    """

    import tempfile
    from pathlib import Path

    from finreason_solver import build_solvers, official
    from finreason_solver.numbers import (
        fraction_to_decimal,
        gold_fraction,
        is_terminating,
    )
    from finreason_solver.predict import predict_split, write_predictions
    from finreason_solver.shapes import ShapeIndex
    from finreason_task1.contracts import _validate_decimal_text

    split = _dev()
    records, _ = predict_split(split, build_solvers.load(), ShapeIndex.load(), None)

    def exactly_right(ours: str, gold: str, spec) -> bool:
        if spec["type"] == "enum":
            return ours == gold
        if spec["rounding"]["mode"] == "exact":
            return gold_fraction(ours) == gold_fraction(gold)
        places = int(spec["rounding"]["decimal_places"])
        return Decimal(ours) == fraction_to_decimal(gold_fraction(gold), places)

    right_finals = right_slots = right_repeating = emitted = 0
    for record in records:
        question = split.questions[record["case_id"]]
        instance = to_instance(question, split.gold[record["case_id"]], None)
        checks = []
        if record["final_answer"] is not None:
            checks.append(
                (record["final_answer"]["value"], instance.final_text, question["answer_spec"], True)
            )
        positions = {
            slot["slot_id"]: index
            for index, slot in enumerate(question["trace_spec"]["slots"])
        }
        for step in record["steps"]:
            position = positions[step["slot_id"]]
            spec = question["trace_spec"]["slots"][position]["result_spec"]
            checks.append((step["value"], instance.slot_texts[position], spec, False))
        for ours, gold, spec, is_final in checks:
            emitted += 1
            if spec["type"] == "enum":
                assert ours in spec["allowed_values"], (record["case_id"], ours)
            else:
                assert _validate_decimal_text(ours, spec) is None, (record["case_id"], ours)
            if not exactly_right(ours, gold, spec):
                continue
            assert scoring.value_matches(ours, gold, spec), (record["case_id"], ours, gold)
            if is_final:
                right_finals += 1
            else:
                right_slots += 1
                if (
                    spec["type"] != "enum"
                    and spec["rounding"]["mode"] == "exact"
                    and not is_terminating(gold_fraction(ours))
                ):
                    assert "/" in ours, ours
                    right_repeating += 1

    assert emitted > 700
    assert right_repeating > 0, "the a/b branch was never exercised"

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "emitted.jsonl"
        write_predictions(records, path)
        report = official.score_dev(path)
    assert report["_exit_code"] == 0
    assert report["counts"]["matched_slots"] == right_slots
    assert report["counts"]["matched_final_answers"] == right_finals

# SPDX-License-Identifier: Apache-2.0
"""Stage 4: the closed forms recovered from the published FinChain generators.

These solvers were written down by reading the benchmark's own generator
source rather than induced by search, so the tests here are the ship gate and
nothing else: every registered form must reproduce all 11 gold instances of its
template, component by component, or it must not ship.  Two further tests guard
the thing a hand-written form could go wrong in a way a search cannot -- a
memorised answer, or a stale registry key -- and one pins the build hook.
"""

from __future__ import annotations

import copy
import json
from fractions import Fraction

import pytest

from finreason_solver import build_solvers, config, expr as E, genforms
from finreason_solver.dataio import labelled_instances
from finreason_solver.derive import TemplateSolver, contract_test, evaluate_solver

pytestmark = pytest.mark.skipif(
    not config.SOLVERS_JSON.exists(),
    reason="run `python -m finreason_solver build-solvers` first",
)

# Every literal any recovered form is allowed to contain.  Percent conversions,
# the growth-factor 1, the zero floor of a payoff, and forecast-year exponents.
# Nothing template-specific, and in particular nothing that could carry a gold
# answer: a memorised value could not hide inside this set.
ALLOWED_CONSTANTS = {
    Fraction(0),
    Fraction(1),
    Fraction(2),
    Fraction(3),
    Fraction(4),
    Fraction(5),
    Fraction(100),
}


@pytest.fixture(scope="module")
def payloads() -> dict[str, dict]:
    return {
        item["template_id"]: item
        for item in json.loads(config.SOLVERS_JSON.read_text())
    }


@pytest.fixture(scope="module")
def groups() -> dict:
    return labelled_instances()


def _candidate(template_id: str, payloads: dict, groups: dict):
    form = genforms.FORMS[template_id]
    incumbent = TemplateSolver.from_json(payloads[template_id])
    return genforms.candidate_solver(form, incumbent, groups[template_id])


def _constants(expression) -> list[Fraction]:
    if expression is None:
        return []
    head = expression[0]
    if head == "c":
        return [Fraction(int(expression[1]), int(expression[2]))]
    if head in ("p", "s"):
        return []
    if head in ("neg", "abs"):
        return _constants(expression[1])
    if head in ("ifge", "ifgt"):
        return (
            _constants(expression[1])
            + _constants(expression[2])
            + _constants(expression[3])
        )
    return _constants(expression[1]) + _constants(expression[2])


@pytest.mark.parametrize("template_id", sorted(genforms.FORMS))
def test_form_reproduces_all_eleven_gold_instances(
    template_id: str, payloads: dict, groups: dict
) -> None:
    """The gate: every component, every instance, exact, or it does not ship."""

    instances = groups[template_id]
    report = contract_test(_candidate(template_id, payloads, groups), instances)
    assert report["n_instances"] == len(instances)
    assert report["final_ok"] == report["n_instances"], report
    assert report["slots_perfect"], report["slot_ok"]


@pytest.mark.parametrize("template_id", sorted(genforms.FORMS))
def test_form_is_shippable_under_the_build_gate(
    template_id: str, payloads: dict, groups: dict
) -> None:
    """The same verdict read through ``build_solvers.is_shippable``."""

    candidate = _candidate(template_id, payloads, groups)
    instances = groups[template_id]
    report = contract_test(candidate, instances)
    payload = build_solvers._finish(candidate, report, payloads[template_id])
    assert build_solvers.is_shippable(payload)
    assert payload["trusted_final"] is True
    assert len(payload["trusted_slots"]) == len(candidate.slots)


@pytest.mark.parametrize("template_id", sorted(genforms.FORMS))
def test_form_carries_no_template_specific_literal(
    template_id: str, payloads: dict, groups: dict
) -> None:
    """No recovered form may hard-code a value; only structural constants."""

    candidate = _candidate(template_id, payloads, groups)
    expressions = [slot.expression for slot in candidate.slots]
    expressions.append(candidate.final_expression)
    for expression in expressions:
        unexpected = [
            value for value in _constants(expression)
            if value not in ALLOWED_CONSTANTS
        ]
        assert unexpected == [], (template_id, unexpected)


@pytest.mark.parametrize("template_id", sorted(genforms.FORMS))
def test_form_answers_vary_with_the_instance(
    template_id: str, payloads: dict, groups: dict
) -> None:
    """A constant would pass no gate here, but pin it anyway."""

    candidate = _candidate(template_id, payloads, groups)
    answers = {
        evaluate_solver(candidate, instance.params, instance.question)[0]
        for instance in groups[template_id]
    }
    assert len(answers) > 1


@pytest.mark.parametrize("template_id", sorted(genforms.FORMS))
def test_form_is_deterministic(
    template_id: str, payloads: dict, groups: dict
) -> None:
    candidate = _candidate(template_id, payloads, groups)
    instance = groups[template_id][0]
    first = evaluate_solver(candidate, instance.params, instance.question)
    second = evaluate_solver(candidate, instance.params, instance.question)
    assert first == second


def test_registry_only_targets_real_templates(groups: dict) -> None:
    assert set(genforms.FORMS) <= set(groups)
    for template_id, form in genforms.FORMS.items():
        assert form.template_id == template_id
        assert form.source and form.note
        n_slots = len(groups[template_id][0].slot_ids)
        assert form.slots, template_id
        assert max(form.slots) < n_slots, template_id


def test_registry_targets_only_templates_the_search_left_open(
    payloads: dict,
) -> None:
    """Stage 4 is a last resort, not a shortcut past the search.

    Read against the pre-stage-4 artifact every registered template is
    unsolved; read against a patched one every registered template is solved.
    Either way the registry must never contain a template the search solved on
    its own and stage 4 then overwrote.
    """

    verdicts = {
        template_id: build_solvers.is_shippable(payloads[template_id])
        for template_id in genforms.FORMS
    }
    assert len(set(verdicts.values())) == 1, verdicts


def test_expressions_evaluate_on_every_instance(payloads: dict, groups: dict) -> None:
    """No form may rely on a slot or parameter an instance does not carry."""

    for template_id in sorted(genforms.FORMS):
        candidate = _candidate(template_id, payloads, groups)
        for instance in groups[template_id]:
            values: list[Fraction] = []
            for slot in candidate.slots:
                assert slot.expression is not None
                values.append(E.evaluate(slot.expression, instance.params, values))
            assert candidate.final_expression is not None
            E.evaluate(candidate.final_expression, instance.params, values)


def test_apply_generator_forms_lifts_the_build_and_is_idempotent(
    payloads: dict,
) -> None:
    """The build hook itself: applied once it ships; applied twice it is stable."""

    by_id = copy.deepcopy(payloads)
    before = sum(1 for item in by_id.values() if build_solvers.is_shippable(item))
    applied = build_solvers.apply_generator_forms(by_id)
    after = sum(1 for item in by_id.values() if build_solvers.is_shippable(item))
    assert after - before == len(applied)
    for template_id in by_id:
        assert build_solvers.is_shippable(by_id[template_id]) or (
            template_id not in genforms.FORMS
        )
    again = build_solvers.apply_generator_forms(by_id)
    assert again == []


@pytest.mark.skipif(
    not config.SHAPE_INDEX_JSON.exists(),
    reason="run `python -m finreason_solver build-index` first",
)
def test_forms_evaluate_legally_on_the_unseen_draws(
    payloads: dict, groups: dict
) -> None:
    """The failure mode a hand-written form is most exposed to.

    A form addresses its inputs positionally, so it is only as good as the
    parameter order staying put on draws nobody has labelled.  Every
    leaderboard and test case that matches one of these templates must produce
    a contract-legal final answer and every one of its trace slots; a shifted
    index would surface here as a missing value rather than in the score.
    """

    from finreason_solver import dataio
    from finreason_solver.predict import predict_case
    from finreason_solver.shapes import ShapeIndex

    index = ShapeIndex.load()
    candidates = {}
    for template_id in genforms.FORMS:
        candidate = _candidate(template_id, payloads, groups)
        report = contract_test(candidate, groups[template_id])
        candidate.trusted_final = bool(report["final_perfect"])
        candidate.trusted_slots = tuple(
            slot_id
            for slot_id, count in report["slot_ok"].items()
            if count == report["n_instances"]
        )
        candidates[template_id] = candidate

    seen = 0
    for loader in (dataio.load_leaderboard, dataio.load_test):
        split = loader()
        matches = index.identify_many(split.questions.values())
        for case_id, question in split.questions.items():
            template_id = matches[case_id].template_id
            if template_id not in candidates:
                continue
            seen += 1
            record = predict_case(
                question, candidates[template_id], None, template_id
            )
            assert record["final_answer"] is not None, (template_id, case_id)
            assert len(record["steps"]) == len(
                question["trace_spec"]["slots"]
            ), (template_id, case_id)
    assert seen == 44

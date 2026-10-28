# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the stage-3 machinery: piecewise expressions, OR/AND
decision lists, derived exponents, sum peeling and the text-rule solvers.

Synthetic tests build small instance vectors with known formulas and assert
the search recovers an expression that reproduces them; the text-rule tests
replay against the cup's own gold instances.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from finreason_solver import expr as E
from finreason_solver import textrules
from finreason_solver.derive import DecisionList, _enum_search, _make_verifier
from finreason_solver.induction import build_pool, evaluate_vector
from finreason_solver.stage3 import Stage3Search

F = Fraction


def _vectors(rows: list[list[int | str | Fraction]]) -> list[tuple[Fraction, ...]]:
    """Columns of ``rows`` as parameter vectors (rows are instances)."""

    return [
        tuple(F(row[index]) for row in rows) for index in range(len(rows[0]))
    ]


# --------------------------------------------------------------------- expr


def test_piecewise_operators_evaluate_both_branches() -> None:
    take_then = ["ifgt", E.param(0), E.param(1), E.param(2)]
    assert E.evaluate(take_then, [F(1), F(10), F(20)]) == F(10)
    assert E.evaluate(take_then, [F(0), F(10), F(20)]) == F(20)
    at_zero = ["ifge", E.param(0), E.param(1), E.param(2)]
    assert E.evaluate(at_zero, [F(0), F(10), F(20)]) == F(10)
    assert E.size(at_zero) == 4
    assert "if" in E.to_text(at_zero)


# ------------------------------------------------------------ decision lists


def test_decision_list_or_and_rules_round_trip_through_json() -> None:
    or_rule = (
        [(E.param(0), ">="), (E.param(1), ">")],
        "or",
        "high",
    )
    and_rule = (
        [(E.param(0), ">"), (E.param(1), ">")],
        "and",
        "medium",
    )
    flat_rule = ([(E.param(2), "<")], "or", "low")
    decision = DecisionList(rules=[or_rule, and_rule, flat_rule], default="none")
    replayed = DecisionList.from_json(decision.to_json())
    for params, expected in [
        ([F(1), F(0), F(1)], "high"),   # first atom of the OR fires
        ([F(-1), F(2), F(1)], "high"),  # second atom of the OR fires
        ([F(-1), F(0), F(1)], "none"),  # AND needs both, < fails
        ([F(-1), F(0), F(-1)], "low"),
    ]:
        assert replayed.evaluate(params, []) == expected
    # Old flat serialisation still loads.
    old = {
        "rules": [{"expr": E.param(0), "comparator": ">=", "label": "yes"}],
        "default": "no",
    }
    assert DecisionList.from_json(old).evaluate([F(1)], []) == "yes"
    assert DecisionList.from_json(old).evaluate([F(-1)], []) == "no"


def test_enum_search_finds_two_atom_or_rule() -> None:
    # label is "flag" when score >= 8 OR override is set; no single sign test
    # over {score-8, override} separates it on these instances.
    rows = [
        [9, 0], [3, 1], [2, 0], [10, 1], [4, 0],
        [8, 0], [1, 1], [5, 0], [6, 0], [7, 1], [2, 1],
    ]
    param_vectors = _vectors(rows)
    labels = [
        "flag" if row[0] >= 8 or row[1] == 1 else "clear" for row in rows
    ]
    n = len(rows)
    threshold = (F(8),) * n
    pool = build_pool(param_vectors + [threshold], [], n)
    verify = _make_verifier(param_vectors + [threshold], [], n)
    decision = _enum_search(pool, labels, ["clear", "flag"], verify)
    assert decision is not None
    for row, expected in zip(rows, labels):
        got = decision.evaluate([F(row[0]), F(row[1]), F(8)], [])
        assert got == expected


# -------------------------------------------------------- stage-3 pool/search


def _stage3_search(param_vectors, n):
    pool = build_pool(param_vectors, [], n, stage3=True)
    verify = _make_verifier(param_vectors, [], n)
    return pool, Stage3Search(pool, param_vectors, [], n, verify), verify


def _exact_check(target):
    return lambda vector: vector == target


def test_stage3_derived_exponent_reaches_quarterly_compounding() -> None:
    # principal, annual rate, years, periods -> P * (1 + r/(100 m)) ** (m n)
    rows = [
        [2222, 12, 3, 4], [1000, 8, 2, 4], [500, 6, 5, 4],
        [1500, 4, 1, 4], [800, 10, 2, 4], [1200, 5, 3, 4],
        [900, 9, 4, 4], [700, 7, 2, 4], [600, 3, 6, 4],
        [400, 2, 3, 4], [2500, 11, 2, 4],
    ]
    param_vectors = _vectors(rows)
    n = len(rows)
    target = tuple(
        F(P) * (1 + F(r, 100 * m)) ** (m * y) for P, r, y, m in rows
    )
    pool, search, verify = _stage3_search(param_vectors, n)
    intervals = [(value, value) for value in target]
    found = search.solve(intervals, _exact_check(target))
    if found is None:
        # The plain pool may already contain it via the derived-exponent pass.
        found = pool.get(target)
    assert found is not None
    assert evaluate_vector(found, param_vectors, [], n) == target


def test_stage3_sum_peeling_recovers_three_term_weighted_sum() -> None:
    # (w1*s1 + w2*s2 + w3*s3) / 100 -- the multi-asset portfolio shape.
    rows = [
        [20, 1, 40, 1, 40, -1], [25, 1, 25, -1, 50, 1], [10, 2, 30, 1, 60, 1],
        [50, 1, 30, -1, 20, 1], [20, -1, 40, 1, 40, 1], [30, 1, 30, 1, 40, -1],
        [15, 2, 45, 1, 40, 1], [35, 1, 25, 1, 40, 1], [40, -1, 20, 1, 40, -1],
        [22, 1, 38, -1, 40, 1], [28, 1, 32, 1, 40, 1],
    ]
    param_vectors = _vectors(rows)
    n = len(rows)
    target = tuple(
        (F(r[0]) * r[1] + F(r[2]) * r[3] + F(r[4]) * r[5]) / 100 for r in rows
    )
    _, search, _ = _stage3_search(param_vectors, n)
    intervals = [(value, value) for value in target]
    found = search.solve(intervals, _exact_check(target))
    assert found is not None
    assert evaluate_vector(found, param_vectors, [], n) == target


def test_stage3_piecewise_recovers_conditional_rebate() -> None:
    # Q = I / P; rebate * Q when Q > T else 0.
    rows = [
        [1000, 15, 1, 66], [2000, 10, 2, 300], [1500, 8, 1, 100],
        [4000, 12, 3, 200], [900, 9, 1, 120], [5000, 10, 4, 450],
        [1200, 15, 2, 60], [2500, 12, 1, 250], [3000, 10, 2, 200],
        [800, 8, 1, 90], [4500, 9, 3, 550],
    ]
    param_vectors = _vectors(rows)
    n = len(rows)

    def value(row):
        quantity = F(row[0], row[1])
        return F(row[2]) * quantity if quantity > row[3] else F(0)

    target = tuple(value(row) for row in rows)
    _, search, _ = _stage3_search(param_vectors, n)
    intervals = [(v, v) for v in target]
    found = search.solve(intervals, _exact_check(target))
    assert found is not None
    assert evaluate_vector(found, param_vectors, [], n) == target


# ---------------------------------------------------------------- text rules


@pytest.fixture(scope="module")
def gold_groups():
    from finreason_solver.dataio import labelled_instances

    return labelled_instances()


@pytest.mark.parametrize("template_id", sorted(textrules.REGISTRY))
def test_text_rules_reproduce_every_gold_instance(template_id, gold_groups) -> None:
    instances = gold_groups.get(template_id)
    if not instances:
        pytest.skip("template not present in this data checkout")
    for instance in instances:
        final, slots = textrules.run(template_id, instance.question)
        assert final == instance.final_text, instance.case_id
        for position, slot_id in enumerate(instance.slot_ids):
            if slot_id in slots:
                assert slots[slot_id] == instance.slot_texts[position], (
                    instance.case_id,
                    slot_id,
                )


def test_text_rules_refuse_to_guess_on_unparseable_text() -> None:
    question = {"question": "Nothing to parse here.", "trace_spec": {"slots": []}}
    final, slots = textrules.run(
        "fp.finance_regulation.kyc.customer_type.basic.v1", question
    )
    assert final is None and slots == {}


# ------------------------------------------------- the reserved piecewise stage


def _conditional_rebate_case():
    """A conditional whose only reachable derivation is the piecewise search."""

    rows = [
        [1000, 15, 1, 66], [2000, 10, 2, 300], [1500, 8, 1, 100],
        [4000, 12, 3, 200], [900, 9, 1, 120], [5000, 10, 4, 450],
        [1200, 15, 2, 60], [2500, 12, 1, 250], [3000, 10, 2, 200],
        [800, 8, 1, 90], [4500, 9, 3, 550],
    ]
    param_vectors = _vectors(rows)
    n = len(rows)

    def value(row):
        quantity = F(row[0], row[1])
        return F(row[2]) * quantity if quantity > row[3] else F(0)

    target = tuple(value(row) for row in rows)
    return param_vectors, n, target


def test_piecewise_still_runs_when_the_shared_budget_is_exhausted() -> None:
    """A saturated sum search must not cancel the conditional search.

    This is the whole reason `carbon_credits.credit_rebate` and
    `carbon_credits.multi_company_synergy` did not ship: their scaled-sum peel
    spends the entire `SOLVE_BUDGET`, and before the reservation `solve()`
    returned before the one stage that can express their answer.
    """

    param_vectors, n, target = _conditional_rebate_case()
    _, search, _ = _stage3_search(param_vectors, n)
    search._budget = 0  # pretend an earlier stage spent everything
    intervals = [(value, value) for value in target]
    found = search.solve(intervals, _exact_check(target))
    assert found is not None
    assert found[0] in ("ifgt", "ifge")
    assert evaluate_vector(found, param_vectors, [], n) == target
    assert search.reserve_used is True


def test_reserved_piecewise_is_still_refusable() -> None:
    """`allow_piecewise=False` must keep meaning what it says."""

    param_vectors, n, target = _conditional_rebate_case()
    _, search, _ = _stage3_search(param_vectors, n)
    search._budget = 0
    intervals = [(value, value) for value in target]
    assert search.solve(intervals, _exact_check(target), allow_piecewise=False) is None
    assert search.reserve_used is False


def test_reserved_piecewise_is_deterministic_across_repeats() -> None:
    """Same inputs, same expression -- the reservation adds no clock or state."""

    param_vectors, n, target = _conditional_rebate_case()
    intervals = [(value, value) for value in target]
    results = []
    for _ in range(2):
        _, search, _ = _stage3_search(param_vectors, n)
        search._budget = 0
        results.append(search.solve(intervals, _exact_check(target)))
    assert results[0] is not None
    assert results[0] == results[1]


# ------------------------------------------ the reserved structural scales


def _many_quantity_rows():
    """Eleven instances with enough distinct positive quantities that the
    value-sum triples alone can fill MAX_SCALED_PAIR_SCALES."""

    rows = []
    for step in range(11):
        w1, w2 = 20 + step, 30 + (step % 5)
        w3 = 100 - w1 - w2
        rows.append(
            [
                w1, w2, w3,
                1 + step, 2 + step, 3 + step,        # volatilities
                50_000 + 1_000 * step, 200_000 - step,
                90 + step, 100, 4 + step, 11 + step,  # padding quantities
                60_000 + step, 40 + step, 70 + step, 5 + step,
            ]
        )
    return rows


def _percent_weighted_sum_target(rows):
    return tuple(
        (F(r[0]) * r[3] + F(r[1]) * r[4] + F(r[2]) * r[5]) / 100 for r in rows
    )


def test_structural_prepass_finds_a_percent_weighted_sum() -> None:
    """The reserved pre-pass reaches ``(w1*s1 + w2*s2 + w3*s3) / 100`` directly.

    `var.multi_asset` states its own formula in exactly this shape and has 43
    parameters; in the derived scale list its value-sum triples fill
    MAX_SCALED_PAIR_SCALES and the ``/100`` scale never gets a pair search.
    """

    rows = _many_quantity_rows()
    param_vectors = _vectors(rows)
    n = len(rows)
    target = _percent_weighted_sum_target(rows)
    _, search, _ = _stage3_search(param_vectors, n)
    found = search._search_structural_scales(
        [(v, v) for v in target], _exact_check(target)
    )
    assert found is not None
    assert evaluate_vector(found, param_vectors, [], n) == target


def test_structural_prepass_never_spends_the_shared_budget() -> None:
    """Monotonicity: the pre-pass may add an answer but never cost one.

    Moving the hundreds to the *front* of the shared-budget scale list was
    measured to lose `wacc.preferred_capm_wacc`, because the value totals a
    three-weight WACC divides by then ran short.  The pre-pass is charged to its
    own reserve and restores the shared budget exactly, hit or miss.
    """

    rows = _many_quantity_rows()
    param_vectors = _vectors(rows)
    n = len(rows)
    _, search, _ = _stage3_search(param_vectors, n)
    # A target no structural-scale sum can reach: every later stage must see
    # the same shared budget it would have seen without the pre-pass.
    unreachable = tuple(F(10**9 + 7 * i, 13) for i in range(n))
    search._budget = 12_345_678
    missed = search._search_structural_scales(
        [(v, v) for v in unreachable], _exact_check(unreachable)
    )
    assert missed is None
    assert search._budget == 12_345_678
    assert search.structural_spent > 0  # it genuinely searched

    target = _percent_weighted_sum_target(rows)
    search._budget = 777
    hit = search._search_structural_scales(
        [(v, v) for v in target], _exact_check(target)
    )
    assert hit is not None
    assert search._budget == 777


def test_old_scale_order_is_unchanged_behind_the_prepass() -> None:
    """The shared-budget scale list keeps its original order: value totals
    (triples, then pairs), then the hundreds, then solved slots."""

    from finreason_solver.stage3 import MAX_SCALED_PAIR_SCALES

    rows = _many_quantity_rows()
    param_vectors = _vectors(rows)
    n = len(rows)
    _, search, _ = _stage3_search(param_vectors, n)
    scales, pair_enabled = search._core_scales()
    assert pair_enabled <= MAX_SCALED_PAIR_SCALES
    hundred = (F(100),) * n
    inside = [vector for vector, _ in scales[:pair_enabled]]
    # Value totals lead; the hundreds never come first in the shared list.
    assert inside and inside[0] != hundred


def test_percent_scaled_three_term_sum_survives_a_crowded_scale_set() -> None:
    """End to end on the shape above: the answer is still recovered."""

    rows = _many_quantity_rows()
    param_vectors = _vectors(rows)
    n = len(rows)
    target = tuple(
        (F(r[0]) * r[3] + F(r[1]) * r[4] + F(r[2]) * r[5]) / 100 for r in rows
    )
    _, search, _ = _stage3_search(param_vectors, n)
    found = search.solve([(v, v) for v in target], _exact_check(target))
    assert found is not None
    assert evaluate_vector(found, param_vectors, [], n) == target

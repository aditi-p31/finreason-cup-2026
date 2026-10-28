# SPDX-License-Identifier: Apache-2.0
"""Serialisation must match the organiser contract exactly."""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
import pytest

from finreason_solver.numbers import (  # noqa: E402
    exact_decimal_text,
    extract_numbers,
    fraction_to_decimal,
    gold_fraction,
    is_terminating,
    mask_numbers,
    render_exact,
    render_for_spec,
    serialisable,
)
from finreason_task1.contracts import _validate_decimal_text  # noqa: E402

EXACT_SPEC = {"type": "decimal", "rounding": {"mode": "exact"}, "unit": "usd"}
TWO_DP_SPEC = {
    "type": "decimal",
    "rounding": {"mode": "half_up", "decimal_places": 2},
    "unit": "usd",
}


def test_rational_tokens_are_one_number() -> None:
    text = "sentiment is -3/17, weight is 0.15.\n\nAnswer format: ..."
    assert [str(value) for value in extract_numbers(text)] == ["-3/17", "3/20"]
    assert mask_numbers(text) == "sentiment is <N>, weight is <N>."


def test_thousand_separators_and_negatives() -> None:
    values = extract_numbers("assets 1,250,000 and delta -12.5")
    assert values == [Fraction(1250000), Fraction(-25, 2)]


@pytest.mark.parametrize(
    "value",
    [
        Fraction(0),
        Fraction(5000),
        Fraction(-5000),
        Fraction(1, 8),
        Fraction(-3, 16),
        Fraction(1, 3),
        Fraction(-2, 7),
        Fraction(1007030781, 1000000),
    ],
)
def test_render_exact_is_contract_legal(value: Fraction) -> None:
    text = render_exact(value)
    assert _validate_decimal_text(text, EXACT_SPEC) is None
    assert gold_fraction(text) == value


def test_terminating_values_never_render_as_rationals() -> None:
    assert render_exact(Fraction(1, 8)) == "0.125"
    assert "/" not in render_exact(Fraction(250, 2))


def test_non_terminating_values_render_irreducible() -> None:
    assert render_exact(Fraction(2, 6)) == "1/3"
    assert render_exact(Fraction(-4, 6)) == "-2/3"


def test_half_up_matches_scorer_direction() -> None:
    assert fraction_to_decimal(Fraction(5, 1000), 2) == Decimal("0.01")
    assert fraction_to_decimal(Fraction(-5, 1000), 2) == Decimal("-0.01")
    assert fraction_to_decimal(Fraction(15, 1000), 2) == Decimal("0.02")


def test_negative_zero_is_normalised() -> None:
    assert str(fraction_to_decimal(Fraction(-1, 10000), 2)) == "0.00"


def test_render_for_spec_two_dp_pads() -> None:
    assert render_for_spec(Fraction(5000), TWO_DP_SPEC) == "5000.00"
    assert _validate_decimal_text("5000.00", TWO_DP_SPEC) is None


def test_serialisable_rejects_oversized_values() -> None:
    assert serialisable(Fraction(10) ** 50, TWO_DP_SPEC)
    assert not serialisable(Fraction(10) ** 400, TWO_DP_SPEC)


def test_is_terminating() -> None:
    assert is_terminating(Fraction(1, 40))
    assert not is_terminating(Fraction(1, 30))
    assert exact_decimal_text(Fraction(1, 40)) == "0.025"

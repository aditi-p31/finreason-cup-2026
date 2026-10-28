# SPDX-License-Identifier: Apache-2.0
"""Exact numeric parsing, extraction and cup-contract serialisation.

Everything downstream of question parsing is a :class:`fractions.Fraction`.
Floats are never used, so the arithmetic matches the organiser scorer, which
compares slot values with exact ``Fraction`` equality and final answers after a
``ROUND_HALF_UP`` quantize.
"""

from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP, localcontext
from fractions import Fraction
from typing import Any, Mapping, Sequence

# Matches integers, decimals, thousand-separated integers and the ``a/b``
# rationals the cup embeds in some crypto-sentiment questions.  The rational
# alternative must come first or ``-3/17`` tokenises as two numbers.
NUMBER_RE = re.compile(
    r"-?\d+(?:,\d+)*(?:\.\d+)?(?:/\d+(?:,\d+)*(?:\.\d+)?)?"
)

# Nine templates hinge on a literal ``true``/``false`` written into the
# scenario ("High-risk override is true").  Those are parameters as much as the
# numbers are, so they are lifted into the same vector as 1 and 0 -- appended
# after the numeric ones so numeric positions never shift.
BOOLEAN_RE = re.compile(r"\b(true|false)\b")

ANSWER_FORMAT_MARKER = "\n\nAnswer format:"

# Serialisation guards mirroring finreason_task1.contracts.
MAX_SIGNIFICANT_DIGITS = 64
MIN_ADJUSTED_EXPONENT = -100
MAX_ADJUSTED_EXPONENT = 100


def question_body(question_text: str) -> str:
    """Drop the boilerplate answer-format tail shared by every case."""

    return question_text.split(ANSWER_FORMAT_MARKER, 1)[0]


def parse_number(token: str) -> Fraction:
    token = token.replace(",", "")
    if "/" in token:
        numerator, denominator = token.split("/", 1)
        return Fraction(Decimal(numerator)) / Fraction(Decimal(denominator))
    return Fraction(Decimal(token))


def extract_numbers(question_text: str) -> list[Fraction]:
    """Ordered numeric parameters of a question, boilerplate tail excluded."""

    body = question_body(question_text)
    values = [parse_number(match.group(0)) for match in NUMBER_RE.finditer(body)]
    values.extend(
        Fraction(1) if match.group(0) == "true" else Fraction(0)
        for match in BOOLEAN_RE.finditer(body)
    )
    return values


def mask_numbers(question_text: str) -> str:
    """Number-masked *shape* of a question body."""

    return NUMBER_RE.sub("<N>", question_body(question_text))


def canonical_decimal(text: str, spec: Mapping[str, Any]) -> Decimal:
    """Reimplementation of the scorer's final-answer canonicalisation."""

    value = Decimal(text)
    rounding = spec["rounding"]
    if rounding["mode"] == "half_up":
        quantum = Decimal(1).scaleb(-rounding["decimal_places"])
        with localcontext() as context:
            context.prec = 256
            value = value.quantize(quantum, rounding=ROUND_HALF_UP)
    if value.is_zero():
        value = abs(value)
    return value


MAX_ROUNDING_PRECISION = 4000


def fraction_to_decimal(value: Fraction, places: int) -> Decimal:
    """Round an exact Fraction half-up to ``places`` decimals.

    ``Decimal.quantize`` raises when the quantised result needs more digits
    than the context precision, so the precision is sized to the value instead
    of pinned at a constant.
    """

    integer_digits = max(
        value.numerator.bit_length() - value.denominator.bit_length(), 0
    )
    integer_digits = int(integer_digits * 0.302) + 2
    precision = integer_digits + places + 40
    if precision > MAX_ROUNDING_PRECISION:
        raise ValueError("value too large to round")
    with localcontext() as context:
        context.prec = precision
        quotient = Decimal(value.numerator) / Decimal(value.denominator)
        quantum = Decimal(1).scaleb(-places)
        result = quotient.quantize(quantum, rounding=ROUND_HALF_UP)
    if result.is_zero():
        result = abs(result)
    return result


def is_terminating(value: Fraction) -> bool:
    denominator = value.denominator
    while denominator % 2 == 0:
        denominator //= 2
    while denominator % 5 == 0:
        denominator //= 5
    return denominator == 1


def exact_decimal_text(value: Fraction) -> str:
    """Finite decimal rendering of a terminating Fraction, no exponent."""

    if not is_terminating(value):
        raise ValueError("value does not terminate in base 10")
    denominator = value.denominator
    twos = 0
    fives = 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    places = max(twos, fives)
    scaled = value.numerator * (10**places) // value.denominator
    sign = "-" if scaled < 0 else ""
    digits = str(abs(scaled))
    if places == 0:
        return sign + digits
    digits = digits.rjust(places + 1, "0")
    whole, frac = digits[:-places], digits[-places:]
    frac = frac.rstrip("0")
    return sign + whole + ("." + frac if frac else "")


def render_exact(value: Fraction) -> str:
    """Serialise a slot value under the cup's ``rounding.mode == "exact"`` rule.

    Terminating values MUST be finite decimals; non-terminating values MUST be
    irreducible ``numerator/denominator`` rationals.  ``finreason_task1``
    rejects a submission that gets this backwards.
    """

    if is_terminating(value):
        return exact_decimal_text(value)
    return f"{value.numerator}/{value.denominator}"


def render_for_spec(value: Fraction, spec: Mapping[str, Any]) -> str:
    """Serialise a value for either a final answer or a trace slot."""

    if spec.get("type") == "enum":
        raise ValueError("enum values are not numeric")
    rounding = spec.get("rounding", {})
    if rounding.get("mode") == "exact":
        return render_exact(value)
    places = int(rounding["decimal_places"])
    return format(fraction_to_decimal(value, places), "f")


def serialisable(value: Fraction, spec: Mapping[str, Any]) -> bool:
    """Whether ``render_for_spec`` will produce a contract-legal string."""

    try:
        text = render_for_spec(value, spec)
    except (ValueError, ArithmeticError, OverflowError):
        return False
    rounding = spec.get("rounding", {})
    if rounding.get("mode") == "exact" and "/" in text:
        numerator, denominator = text.split("/", 1)
        return (
            len(numerator.lstrip("-")) <= MAX_SIGNIFICANT_DIGITS
            and len(denominator) <= MAX_SIGNIFICANT_DIGITS
        )
    coefficient = text.lstrip("-")
    digits = coefficient.replace(".", "").lstrip("0") or "0"
    if len(digits) > MAX_SIGNIFICANT_DIGITS:
        return False
    parsed = Decimal(text)
    if parsed and not MIN_ADJUSTED_EXPONENT <= parsed.adjusted() <= MAX_ADJUSTED_EXPONENT:
        return False
    return True


def gold_fraction(text: str) -> Fraction:
    """Parse a gold slot value string (decimal or ``a/b``) exactly."""

    if "/" in text:
        numerator, denominator = text.split("/", 1)
        return Fraction(int(numerator), int(denominator))
    return Fraction(Decimal(text))


def decimal_places_of(spec: Mapping[str, Any]) -> int | None:
    rounding = spec.get("rounding") or {}
    if rounding.get("mode") == "half_up":
        return int(rounding["decimal_places"])
    return None


def all_equal(values: Sequence[Any]) -> bool:
    return all(value == values[0] for value in values)

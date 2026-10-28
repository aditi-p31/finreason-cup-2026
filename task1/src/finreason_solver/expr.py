# SPDX-License-Identifier: Apache-2.0
"""A tiny exact-arithmetic expression language for induced solvers.

An expression is a JSON-serialisable nested list so a whole solver program can
be written to ``artifacts/solvers.json`` and replayed without any code
generation.  Every evaluation is over :class:`fractions.Fraction`; no float
ever enters the pipeline.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any, Sequence

# Guard against denominator blow-up in the induction search.
MAX_BITS = 2048


class Unevaluable(Exception):
    """Raised when an expression cannot be evaluated on given inputs."""


def const(value: Fraction) -> list[Any]:
    return ["c", str(value.numerator), str(value.denominator)]


def param(index: int) -> list[Any]:
    return ["p", index]


def slot(index: int) -> list[Any]:
    return ["s", index]


def evaluate(
    expr: Sequence[Any],
    params: Sequence[Fraction],
    slots: Sequence[Fraction] = (),
) -> Fraction:
    head = expr[0]
    if head == "c":
        return Fraction(int(expr[1]), int(expr[2]))
    if head == "p":
        index = expr[1]
        if index >= len(params):
            raise Unevaluable(f"parameter {index} missing")
        return params[index]
    if head == "s":
        index = expr[1]
        if index >= len(slots):
            raise Unevaluable(f"slot {index} missing")
        return slots[index]
    if head == "neg":
        return -evaluate(expr[1], params, slots)
    if head == "abs":
        return abs(evaluate(expr[1], params, slots))
    if head in ("ifge", "ifgt"):
        # Piecewise arithmetic: ``cond >= 0 ? then : else`` (strict for ifgt).
        # This is how "return X when Q exceeds T and zero otherwise" questions
        # are expressed; < and <= forms are the same node with branches swapped.
        condition = evaluate(expr[1], params, slots)
        taken = condition >= 0 if head == "ifge" else condition > 0
        return evaluate(expr[2] if taken else expr[3], params, slots)
    left = evaluate(expr[1], params, slots)
    right = evaluate(expr[2], params, slots)
    if head == "+":
        return left + right
    if head == "-":
        return left - right
    if head == "*":
        return left * right
    if head == "/":
        if right == 0:
            raise Unevaluable("division by zero")
        return left / right
    if head == "^":
        if right.denominator != 1:
            raise Unevaluable("non-integer exponent")
        exponent = int(right)
        if left == 0 and exponent < 0:
            raise Unevaluable("zero to a negative power")
        if abs(exponent) > 512:
            raise Unevaluable("exponent out of range")
        return left**exponent
    if head == "min":
        return min(left, right)
    if head == "max":
        return max(left, right)
    raise Unevaluable(f"unknown operator {head!r}")


def size(expr: Sequence[Any]) -> int:
    head = expr[0]
    if head in ("c", "p", "s"):
        return 1
    if head in ("neg", "abs"):
        return 1 + size(expr[1])
    if head in ("ifge", "ifgt"):
        return 1 + size(expr[1]) + size(expr[2]) + size(expr[3])
    return 1 + size(expr[1]) + size(expr[2])


_OP_TEXT = {"+": " + ", "-": " - ", "*": " * ", "/": " / ", "^": " ** "}


def to_text(expr: Sequence[Any], names: Sequence[str] = ()) -> str:
    """Human-readable rendering used in the solver report."""

    head = expr[0]
    if head == "c":
        value = Fraction(int(expr[1]), int(expr[2]))
        return str(value) if value.denominator != 1 else str(value.numerator)
    if head == "p":
        index = expr[1]
        return names[index] if index < len(names) else f"p{index}"
    if head == "s":
        return f"trace_{expr[1] + 1}"
    if head == "neg":
        return f"-({to_text(expr[1], names)})"
    if head == "abs":
        return f"abs({to_text(expr[1], names)})"
    if head in ("ifge", "ifgt"):
        comparator = ">=" if head == "ifge" else ">"
        return (
            f"if {to_text(expr[1], names)} {comparator} 0"
            f" -> {to_text(expr[2], names)}; else -> {to_text(expr[3], names)}"
        )
    left = to_text(expr[1], names)
    right = to_text(expr[2], names)
    if head in ("min", "max"):
        return f"{head}({left}, {right})"
    return f"({left}{_OP_TEXT[head]}{right})"


def too_big(value: Fraction) -> bool:
    return (
        value.numerator.bit_length() > MAX_BITS
        or value.denominator.bit_length() > MAX_BITS
    )

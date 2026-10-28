# SPDX-License-Identifier: Apache-2.0
"""Text-rule solvers for templates whose deciding variable is a word.

Four ``finance_regulation.kyc`` templates key their answer on a categorical
token ("The account nature is minor_account", "The supplied evidence
traceability is low") and state the complete mapping rule inside the question
itself ("The identifiers personal_savings, joint, and minor_account belong to
natural_person and map to individual_customer").  The numeric induction cannot
see words, but the rule is fully machine-readable, so these solvers parse the
mapping *from each question at prediction time* rather than memorising gold
labels; they generalise to fresh draws for the same reason the induced
formulas do.

Every solver here ships through exactly the same gate as an induced solver: it
is replayed against all 11 gold instances of its template by
``derive.contract_test``, and a component is trusted only if it reproduces
every one of them.  A parse failure returns nothing rather than a guess.

Registered by template id; ``derive_template`` attaches the rule name and
``evaluate_solver`` fills only the components the induction left unsolved.
"""

from __future__ import annotations

import re
from fractions import Fraction
from typing import Any, Callable, Mapping

from .numbers import parse_number, question_body

TextResult = tuple[str | None, dict[str, str]]

_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def _number(token: str) -> Fraction:
    token = token.strip().rstrip(".")
    if token.lower() in _WORD_NUMBERS:
        return Fraction(_WORD_NUMBERS[token.lower()])
    return parse_number(token)


def _split_identifiers(blob: str) -> list[str]:
    return [
        stripped
        for token in re.split(r",|\band\b", blob)
        if (stripped := token.strip())
    ]


def _search(pattern: str, text: str) -> re.Match:
    match = re.search(pattern, text)
    if match is None:
        raise ValueError(f"pattern not found: {pattern!r}")
    return match


def _slot_allowed(question: Mapping[str, Any], slot_id: str) -> list[str]:
    for slot in question["trace_spec"]["slots"]:
        if slot["slot_id"] == slot_id:
            return list(slot["result_spec"].get("allowed_values") or [])
    return []


def solve_customer_type(question: Mapping[str, Any]) -> TextResult:
    text = question_body(question["question"])
    nature = _search(r"The account nature is (\w+)\.", text).group(1)
    holders = int(_search(r"The number of account holders is (\d+)\.", text).group(1))
    family: dict[str, str] = {}
    customer: dict[str, str] = {}
    for blob, form, target in re.findall(
        r"The identifiers? ([\w ,]+?) belongs? to (\w+) and maps? to (\w+)\.", text
    ):
        for identifier in _split_identifiers(blob):
            family[identifier] = form
            customer[identifier] = target
    single, multiple = _search(
        r"one holder is (\w+) and more than one holder is (\w+)", text
    ).groups()
    slots = {
        "legal_form_family": family[nature],
        "holder_configuration": single if holders == 1 else multiple,
    }
    return customer[nature], slots


def solve_document_validity(question: Mapping[str, Any]) -> TextResult:
    text = question_body(question["question"])
    submitted = _search(r"The submitted document is (\w+)\.", text).group(1)
    use = _search(r"The requested use is (\w+)\.", text).group(1)
    category: dict[str, str] = {}
    for blob, kind in re.findall(
        r"The identifiers? ([\w ,]+?) (?:are|is) (\w+)\.", text
    ):
        for identifier in _split_identifiers(blob):
            category[identifier] = kind
    accepts: dict[str, set[str]] = {}
    for purpose, first, second in re.findall(
        r"the purpose (\w+) accepts (\w+) or (\w+)", text, flags=re.IGNORECASE
    ):
        accepts[purpose] = {first, second}
    kind = category[submitted]
    final = "true" if kind in accepts[use] else "false"
    return final, {"document_category": kind}


def solve_source_of_funds(question: Mapping[str, Any]) -> TextResult:
    text = question_body(question["question"])
    source = _number(_search(r"source risk score is (-?[\d,./]+)\.", text).group(1))
    jurisdiction = _number(
        _search(r"jurisdiction risk score is (-?[\d,./]+)\.", text).group(1)
    )
    amount = _number(
        _search(r"deposit amount in whole USD is (-?[\d,]+)\.", text).group(1)
    )
    traceability = _search(r"evidence traceability is (\w+)\.", text).group(1)
    route_label, route_amount, route_trace = _search(
        r"The (\w+) route applies exactly when the amount is at least"
        r" USD ([\d,]+) and traceability is (\w+)\.",
        text,
    ).groups()
    high_label, high_threshold, medium_label, medium_threshold, low_label = _search(
        r"Return (\w+) when the total score is at least ([\d,]+) or that"
        r" combination route applies; otherwise return (\w+) when the total is"
        r" at least ([\d,]+); otherwise return (\w+)\.",
        text,
    ).groups()
    total = source + jurisdiction
    route_applies = amount >= _number(route_amount) and traceability == route_trace
    allowed_routes = _slot_allowed(question, "amount_traceability_route")
    route_name = f"{route_label}_route"
    fallback_routes = [value for value in allowed_routes if value != route_name]
    if route_name not in allowed_routes or len(fallback_routes) != 1:
        raise ValueError("route labels do not line up with the slot contract")
    if total >= _number(high_threshold) or route_applies:
        final = high_label
    elif total >= _number(medium_threshold):
        final = medium_label
    else:
        final = low_label
    slots = {
        "total_risk_score": str(total) if total.denominator == 1 else None,
        "amount_traceability_route": route_name if route_applies else fallback_routes[0],
    }
    slots = {key: value for key, value in slots.items() if value is not None}
    return final, slots


def solve_customer_risk_rating(question: Mapping[str, Any]) -> TextResult:
    text = question_body(question["question"])
    residency = _number(
        _search(r"residency risk points are (-?[\d,./]+)\.", text).group(1)
    )
    account_type = _search(r"The account type is (\w+)\.", text).group(1)
    volume = _number(
        _search(r"volume in whole USD is ([\d,]+)\.", text).group(1)
    )
    points_blob = _search(r"Account points are ([\w=, ]+?)\.", text).group(1)
    account_points = {
        name: Fraction(int(value))
        for name, value in re.findall(r"(\w+)=(\d+)", points_blob)
    }
    bands = _search(
        r"Volume points are (\d+) for volume at most USD ([\d,]+),"
        r" (\d+) for volume above USD ([\d,]+) and at most USD ([\d,]+),"
        r" (\d+) for volume above USD ([\d,]+) and at most USD ([\d,]+),"
        r" and (\d+) for volume above USD ([\d,]+)\.",
        text,
    ).groups()
    band1, cap1, band2, low2, cap2, band3, low3, cap3, band4, low4 = bands
    if volume <= _number(cap1):
        volume_points = Fraction(int(band1))
    elif _number(low2) < volume <= _number(cap2):
        volume_points = Fraction(int(band2))
    elif _number(low3) < volume <= _number(cap3):
        volume_points = Fraction(int(band3))
    elif volume > _number(low4):
        volume_points = Fraction(int(band4))
    else:
        raise ValueError("volume bands do not cover the volume")
    bonus_word, bonus_type, bonus_threshold = _search(
        r"a (\w+)-point escalation bonus exactly when account type is (\w+)"
        r" and volume is above USD ([\d,]+)",
        text,
    ).groups()
    escalation = (
        _number(bonus_word)
        if account_type == bonus_type and volume > _number(bonus_threshold)
        else Fraction(0)
    )
    total = residency + account_points[account_type] + volume_points + escalation
    low_label, low_cap, medium_label, medium_low, medium_high, high_label, high_floor = _search(
        r"Return (\w+) for a total at most ([\d,]+), (\w+) for a total from"
        r" ([\d,]+) through ([\d,]+) inclusive, and (\w+) for a total of at"
        r" least ([\d,]+)\.",
        text,
    ).groups()
    if total <= _number(low_cap):
        final = low_label
    elif _number(medium_low) <= total <= _number(medium_high):
        final = medium_label
    elif total >= _number(high_floor):
        final = high_label
    else:
        raise ValueError("total bands do not cover the total")
    slots = {
        "volume_risk_points": str(volume_points),
        "escalation_bonus": str(escalation),
        "total_risk_points": str(total),
    }
    return final, slots


REGISTRY: dict[str, Callable[[Mapping[str, Any]], TextResult]] = {
    "fp.finance_regulation.kyc.customer_type.basic.v1": solve_customer_type,
    "fp.finance_regulation.kyc.document_validity.basic.v1": solve_document_validity,
    "fp.finance_regulation.kyc.source_of_funds.intermediate.v1": solve_source_of_funds,
    "fp.finance_regulation.kyc.customer_risk_rating.advanced.v1": solve_customer_risk_rating,
}


def run(template_id: str, question: Mapping[str, Any]) -> TextResult:
    """Run a registered text solver; parse failures yield nothing, never a guess."""

    solver = REGISTRY.get(template_id)
    if solver is None:
        return None, {}
    try:
        return solver(question)
    except (ValueError, KeyError, ArithmeticError, AttributeError, IndexError):
        return None, {}

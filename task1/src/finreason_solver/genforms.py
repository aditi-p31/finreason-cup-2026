# SPDX-License-Identifier: Apache-2.0
"""Generator-recovered closed forms for templates the search could not reach.

Eleven of the 290 templates state an arithmetic that the staged value-vector
search does not close inside its deterministic work budget: five-term growing
DCFs with a Gordon terminal, double-capped deal terms, a Fisher conversion in
front of a three-weight WACC sum, and piecewise carbon-credit rebates.

Every one of those templates is a rewrite of a *published* FinChain generator
function (``mbzuai-nlp/finchain``, ``data/templates/<domain>/<topic>.py``),
which is the benchmark's own declared source taxonomy.  Reading the generator
recovers the intended computation directly, so this module writes each one down
once, in the same expression language the induced solvers use, over the same
positional parameter vector.

Nothing here is trusted because it was written down.  A form is turned into a
:class:`~finreason_solver.derive.TemplateSolver` and replayed against all 11
gold instances by :func:`derive.contract_test`, exactly like an induced solver,
and ships per component on that gate alone.  A form that misreads its generator
simply fails and changes nothing.

No FinChain code is executed and no FinChain output is used as an oracle: the
generators are read as documentation and the cup's own gold files arbitrate.
Where the cup's rewritten wording diverges from the generator (the cup supplies
the VaR time multiplier directly instead of taking a square root; it publishes
different trace slots for the two three-year DCFs), the gold instances win and
the form below follows them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Sequence

from . import expr as E

Expr = list[Any]


# --- expression construction helpers ---------------------------------------


def P(index: int) -> Expr:
    """The ``index``-th number lifted out of the question body."""

    return E.param(index)


def S(position: int) -> Expr:
    """The 0-based trace slot ``position`` of the same template."""

    return E.slot(position)


def C(numerator: int, denominator: int = 1) -> Expr:
    return E.const(Fraction(numerator, denominator))


def add(*terms: Expr) -> Expr:
    result = terms[0]
    for term in terms[1:]:
        result = ["+", result, term]
    return result


def sub(left: Expr, right: Expr) -> Expr:
    return ["-", left, right]


def mul(*factors: Expr) -> Expr:
    result = factors[0]
    for factor in factors[1:]:
        result = ["*", result, factor]
    return result


def div(left: Expr, right: Expr) -> Expr:
    return ["/", left, right]


def power(base: Expr, exponent: Expr) -> Expr:
    return ["^", base, exponent]


def mx(left: Expr, right: Expr) -> Expr:
    return ["max", left, right]


def mn(left: Expr, right: Expr) -> Expr:
    return ["min", left, right]


def ifgt(condition: Expr, then: Expr, otherwise: Expr) -> Expr:
    """``condition > 0 ? then : otherwise`` -- strict, as the questions state."""

    return ["ifgt", condition, then, otherwise]


def pct(index: int) -> Expr:
    """A percentage parameter as a ratio: ``pN / 100``."""

    return div(P(index), C(100))


def growth(index: int) -> Expr:
    """``1 + pN/100``, the growth or discount factor of a percentage rate."""

    return add(C(1), pct(index))


@dataclass(frozen=True)
class TemplateForm:
    """One template's recovered computation.

    ``slots`` maps a 0-based trace position to its expression; ``final`` is the
    answer expression.  A position left out keeps whatever the induced solver
    already validated for it.
    """

    template_id: str
    source: str  # the FinChain generator this was read from
    note: str
    slots: dict[int, Expr] = field(default_factory=dict)
    final: Expr | None = None


def _dcf_pv_sum(cash_flows: Sequence[int], rate_index: int) -> Expr:
    """``sum_t FCF_t / (1 + r)^t`` for cash flows given at p``cash_flows[t-1]``."""

    factor = growth(rate_index)
    terms = [
        div(P(index), power(factor, C(year)))
        for year, index in enumerate(cash_flows, start=1)
    ]
    return add(*terms)


def _gordon_terminal(fcf: Expr, rate_index: int, growth_index: int) -> Expr:
    """``FCF * (1 + g) / (r - g)`` with both rates stated in percent."""

    return div(
        mul(fcf, growth(growth_index)),
        sub(pct(rate_index), pct(growth_index)),
    )


def _build_forms() -> dict[str, TemplateForm]:
    forms: list[TemplateForm] = []

    # --- sustainable_finance -------------------------------------------------

    # finchain sustainable_finance/carbon_credits.py::template_carbon_credit_rebate
    #   credits = investment / price; rebate applied only when credits > threshold.
    # p0 investment, p3 unit price, p6 rebate rate, p9 threshold.
    forms.append(
        TemplateForm(
            template_id="fp.sustainable_finance.carbon_credits.credit_rebate.basic.v1",
            source="sustainable_finance/carbon_credits.py::template_carbon_credit_rebate",
            note="Q = I/P; rebate = Q*rate, paid only when Q > T (equality does not qualify).",
            slots={0: div(P(0), P(3)), 1: mul(S(0), P(6))},
            final=ifgt(sub(S(0), P(9)), S(1), C(0)),
        )
    )

    # finchain .../carbon_credits.py::template_multi_company_synergy
    # p1, p4 tonnes; p8 unit price; p11 discount percent; p14 credit threshold.
    forms.append(
        TemplateForm(
            template_id="fp.sustainable_finance.carbon_credits.multi_company_synergy.intermediate.v1",
            source="sustainable_finance/carbon_credits.py::template_multi_company_synergy",
            note="gross = (t1+t2)*price; the synergy discount applies only when total credits > threshold.",
            slots={
                0: add(P(1), P(4)),
                1: mul(S(0), P(8)),
                2: mul(S(1), sub(C(1), pct(11))),
            },
            final=ifgt(sub(S(0), P(14)), S(2), S(1)),
        )
    )

    # finchain sustainable_finance/green_bonds.py
    #   ::template_green_bond_advanced_comprehensive_analysis
    # p0 principal, p3 coupon %, p6 years, p9 tax-credit %, p12 annual savings,
    # p15 bonus per block, p16 block size, p19 reinvested %, p22 reinvest rate %.
    # The per-year reinvestment sum sum_{i=1..T} (1+q)^(T-i) is the geometric
    # series (x^T - 1)/(x - 1) with x = 1 + q, and q >= 2 percent by the stated
    # range so the denominator is never zero.
    reinvest_amount = mul(pct(19), div(S(0), P(6)))
    geometric = div(sub(power(growth(22), P(6)), C(1)), pct(22))
    forms.append(
        TemplateForm(
            template_id="fp.sustainable_finance.green_bonds.comprehensive_analysis.advanced.v1",
            source="sustainable_finance/green_bonds.py::template_green_bond_advanced_comprehensive_analysis",
            note=(
                "interest = P*((1+c)^T - 1); bonus = (savings/block)*rate*T; "
                "reinvestment = (pct*interest/T) * geometric sum of (1+q)^k, k=0..T-1; "
                "total = interest + tax credit + bonus + reinvestment."
            ),
            slots={
                0: mul(P(0), sub(power(growth(3), P(6)), C(1))),
                1: mul(div(P(12), P(16)), P(15), P(6)),
                2: mul(reinvest_amount, geometric),
            },
            final=add(S(0), mul(S(0), pct(9)), S(1), S(2)),
        )
    )

    # --- mergers_and_acquisitions -------------------------------------------

    # finchain mergers_and_acquisitions/valuation_methods.py
    #   ::template_dcf_three_year_terminal_to_equity
    # p2..p4 FCF years 1-3, p5 discount %, p6 terminal growth %, p7 debt, p8 cash.
    # The cup publishes PV(forecasts) and PV(terminal) as the two trace slots.
    discounted_terminal = div(
        _gordon_terminal(P(4), 5, 6), power(growth(5), C(3))
    )
    forms.append(
        TemplateForm(
            template_id="fp.mergers_and_acquisitions.valuation_methods.dcf_three_year_terminal_to_equity.intermediate.v1",
            source="mergers_and_acquisitions/valuation_methods.py::template_dcf_three_year_terminal_to_equity",
            note="PV of three FCFs; PV of the Gordon terminal; equity = both minus debt plus cash.",
            slots={0: _dcf_pv_sum((2, 3, 4), 5), 1: discounted_terminal},
            final=add(sub(add(S(0), S(1)), P(7)), P(8)),
        )
    )

    # finchain .../valuation_methods.py::template_dcf_3yr_gordon_to_equity
    # Same inputs; the cup publishes the *undiscounted* terminal value and the
    # enterprise value as its two trace slots instead.
    forms.append(
        TemplateForm(
            template_id="fp.mergers_and_acquisitions.valuation_methods.dcf_3yr_gordon_to_equity.advanced.v1",
            source="mergers_and_acquisitions/valuation_methods.py::template_dcf_3yr_gordon_to_equity",
            note="terminal value at year 3; enterprise value = PV(FCFs) + PV(TV); equity = EV - net debt.",
            slots={
                0: _gordon_terminal(P(4), 5, 6),
                1: add(
                    _dcf_pv_sum((2, 3, 4), 5),
                    div(S(0), power(growth(5), C(3))),
                ),
            },
            final=sub(S(1), sub(P(7), P(8))),
        )
    )

    # finchain mergers_and_acquisitions/due_diligence.py
    #   ::template_due_diligence_dcf_valuation
    # p1 Year-1 FCF, p2 forecast growth %, p5 discount %, p6 terminal growth %.
    # The generator fixes the horizon at five years, so the forecast strip is a
    # five-term sum FCF1*(1+g)^(t-1) / (1+r)^t.
    forecast_strip = add(
        *[
            div(
                mul(P(1), power(growth(2), C(year - 1))),
                power(growth(5), C(year)),
            )
            for year in range(1, 6)
        ]
    )
    forms.append(
        TemplateForm(
            template_id="fp.mergers_and_acquisitions.due_diligence.due_diligence_dcf_valuation.advanced.v1",
            source="mergers_and_acquisitions/due_diligence.py::template_due_diligence_dcf_valuation",
            note="five-year growing FCF strip discounted year by year, plus the Gordon terminal discounted five years.",
            slots={
                0: mul(P(1), power(growth(2), C(4))),
                1: _gordon_terminal(S(0), 5, 6),
            },
            final=add(forecast_strip, div(S(1), power(growth(5), C(5)))),
        )
    )

    # finchain mergers_and_acquisitions/deal_structure.py
    #   ::template_earnout_with_bonus_calculation
    # p0 base price, p1 earn-out maximum, p2 target revenue, p3 actual revenue,
    # p4 bonus rate %, p5 bonus cap, p6 threshold percent of target (110).
    excess = mx(sub(P(3), mul(P(2), pct(6))), C(0))
    forms.append(
        TemplateForm(
            template_id="fp.mergers_and_acquisitions.deal_structure.earnout_with_bonus_calculation.intermediate.v1",
            source="mergers_and_acquisitions/deal_structure.py::template_earnout_with_bonus_calculation",
            note="prorated earn-out capped at its maximum; bonus on revenue above 110% of target, capped at the bonus cap.",
            slots={
                0: mn(P(1), div(mul(P(1), P(3)), P(2))),
                1: mn(P(5), mul(excess, pct(4))),
            },
            final=add(P(0), S(0), S(1)),
        )
    )

    # finchain .../deal_structure.py::template_leveraged_buyout_adjusted_shares_calculation
    # p0 deal value, p1 debt %, p2 share price, p3 price threshold, p4 bonus factor.
    forms.append(
        TemplateForm(
            template_id="fp.mergers_and_acquisitions.deal_structure.leveraged_buyout_adjusted_shares_calculation.intermediate.v1",
            source="mergers_and_acquisitions/deal_structure.py::template_leveraged_buyout_adjusted_shares_calculation",
            note="equity slice / share price; the 5 percent bonus applies only strictly below the price threshold.",
            slots={0: mul(P(0), sub(C(1), pct(1))), 1: div(S(0), P(2))},
            final=ifgt(sub(P(3), P(2)), mul(S(1), P(4)), S(1)),
        )
    )

    # --- risk_management -----------------------------------------------------

    # finchain risk_management/var.py::template_multi_asset_var
    # p0 portfolio value; p2/p4/p6 weights %; p8/p10/p12 volatilities %;
    # p13 time multiplier (the cup supplies it directly instead of sqrt(days));
    # p14 confidence %, p15 the literal 100.
    forms.append(
        TemplateForm(
            template_id="fp.risk_management.var.multi_asset.intermediate.v1",
            source="risk_management/var.py::template_multi_asset_var",
            note="S = (w1*s1 + w2*s2 + w3*s3)/100; VaR = V * (S/100) * t * (1 + (100-c)/100).",
            slots={
                0: div(
                    add(mul(P(2), P(8)), mul(P(4), P(10)), mul(P(6), P(12))),
                    C(100),
                ),
                1: div(S(0), C(100)),
                2: add(C(1), sub(C(1), div(P(14), C(100)))),
            },
            final=mul(P(0), S(1), P(13), S(2)),
        )
    )

    # --- financial_markets ---------------------------------------------------

    # The cup rewrote finchain's option_pricing hard scenario as a one-period
    # binomial call and states the whole recipe in the question body:
    # p0 spot, p1 strike, p2 up multiplier, p3 down multiplier, p4 rate %.
    discount = growth(4)
    up_probability = div(sub(discount, P(3)), sub(P(2), P(3)))
    forms.append(
        TemplateForm(
            template_id="fp.financial_markets.option_pricing.one_period_binomial_call.intermediate.v1",
            source="financial_markets/option_pricing.py::template_op_hard1 (cup rewrite: one-period binomial)",
            note="payoffs max(S*u-K,0) and max(S*d-K,0); q = ((1+r)-d)/(u-d); C = (q*Cu + (1-q)*Cd)/(1+r).",
            slots={
                0: mx(sub(mul(P(0), P(2)), P(1)), C(0)),
                1: mx(sub(mul(P(0), P(3)), P(1)), C(0)),
                2: up_probability,
            },
            final=div(
                add(mul(S(2), S(0)), mul(sub(C(1), S(2)), S(1))),
                discount,
            ),
        )
    )

    # --- corporate_finance ---------------------------------------------------

    # finchain corporate_finance/wacc.py::template_inflation_adjusted_capm_wacc
    # p0 equity, p1/p2 the two debt tranches, p3 beta, p4 nominal market return %,
    # p5 inflation %, p6 real risk-free %, p7/p8 tranche costs %, p9 tax %.
    real_market = mul(C(100), sub(div(growth(4), growth(5)), C(1)))
    total_debt = add(P(1), P(2))
    forms.append(
        TemplateForm(
            template_id="fp.corporate_finance.wacc.inflation_adjusted_capm_wacc.advanced.v1",
            source="corporate_finance/wacc.py::template_inflation_adjusted_capm_wacc",
            note=(
                "Fisher real market return; CAPM equity cost; value-weighted debt cost; "
                "WACC = wE*ke + wD*kd*(1-T)."
            ),
            slots={
                0: real_market,
                1: add(P(6), mul(P(3), sub(S(0), P(6)))),
                2: div(add(mul(P(1), P(7)), mul(P(2), P(8))), total_debt),
            },
            final=div(
                add(
                    mul(P(0), S(1)),
                    mul(total_debt, S(2), sub(C(1), pct(9))),
                ),
                add(P(0), total_debt),
            ),
        )
    )

    return {form.template_id: form for form in forms}


FORMS: dict[str, TemplateForm] = _build_forms()


def _places_of(spec: Any) -> int | None:
    rounding = (spec.get("rounding") or {}) if spec else {}
    if rounding.get("mode") == "half_up":
        return int(rounding["decimal_places"])
    return None


def candidate_solver(form: TemplateForm, incumbent, instances: Sequence[Any]) -> Any:
    """A :class:`TemplateSolver` carrying ``form`` over ``incumbent``'s shape.

    Slot ids, parameter count and the answer kind come from the incumbent
    solver; rounding places come from the question's own spec, so a proposed
    expression is serialised exactly as the cup asks for that component.  The
    candidate therefore differs from the incumbent only in the arithmetic it
    proposes, and the caller contract-tests the result.
    """

    from .derive import SlotSolver, TemplateSolver

    first = instances[0]
    slot_places = [_places_of(spec) for spec in first.slot_specs]

    candidate = TemplateSolver(
        template_id=incumbent.template_id,
        n_params=incumbent.n_params,
        final_kind=incumbent.final_kind,
        final_expression=incumbent.final_expression,
        final_places=incumbent.final_places,
        final_decision=incumbent.final_decision,
        source="generator-form",
        text_rules=incumbent.text_rules,
    )
    for position, slot in enumerate(incumbent.slots):
        proposed = form.slots.get(position)
        if proposed is None:
            candidate.slots.append(
                SlotSolver(
                    slot_id=slot.slot_id,
                    kind=slot.kind,
                    expression=slot.expression,
                    places=slot.places,
                    decision=slot.decision,
                )
            )
            continue
        places = slot_places[position] if position < len(slot_places) else None
        candidate.slots.append(
            SlotSolver(
                slot_id=slot.slot_id,
                kind="half_up" if places is not None else "exact",
                expression=proposed,
                places=places,
            )
        )
    if form.final is not None and incumbent.final_kind != "enum":
        candidate.final_expression = form.final
    return candidate

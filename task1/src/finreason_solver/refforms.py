# SPDX-License-Identifier: Apache-2.0
"""Reference forms for templates whose labelled draws are degenerate.

The ship gate accepts a component when it reproduces all 11 labelled instances
of its template.  On 101 of the 290 templates those 11 draws carry an exact
relation that the unlabelled draws do not: a weight that is always 1, a
secondary impact that is always 0, a split factor that is always 2, two rates
that are always equal, holdings that always form an arithmetic progression.
Any expression that uses the wrong side of such a relation reproduces every
gold value and ships, and the search, which keeps the *smallest* consistent
expression, reaches for the wrong side whenever it is shorter
(``4 / p1`` for ``p1 / 100`` when ``p1`` is always -20).

Every cup question in these templates states its recipe in words ("Staking
impact equals portfolio value times staking share times yield boost").  Each
form below is that sentence written down in the solver expression language,
over the same positional parameter vector (``pN`` is the Nth number in the
question body, then literal ``true``/``false`` as 1/0; ``sK`` is the 0-based
trace slot K of the same template).  The public FinChain generator was read
alongside wherever the wording left a choice.

A form is trusted for nothing on its own: :func:`reference_solver` builds it
into a :class:`~finreason_solver.derive.TemplateSolver` and the caller replays
it against all 11 gold instances, exactly like an induced solver.

Two registries:

* :data:`REFERENCES` -- every template ``scripts/degeneracy_audit.py`` flags,
  read and written down once.  Used by the audit to decide, on the unlabelled
  leaderboard and test draws, whether the search's choice was the intended one.
* :data:`FIXES` -- the subset where it was not.  Only these ship (build stage
  5, :func:`finreason_solver.build_solvers.apply_reference_forms`); everywhere
  else the search's own program stays, because it agrees with the reference on
  every labelled and unlabelled draw.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Sequence, Union

from . import expr as E

Expr = list[Any]

_OPS = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.Pow: "^"}
_CMP = {ast.Gt: ">", ast.GtE: ">=", ast.Lt: "<", ast.LtE: "<="}


def _number(value: Any) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"unsupported literal {value!r}")
    # repr of a Python float literal is its shortest round-trip text, so
    # 0.105 becomes exactly 21/200 rather than the binary approximation.
    return Fraction(repr(value)) if isinstance(value, float) else Fraction(value)


def _node(node: ast.AST) -> Expr:
    if isinstance(node, ast.Expression):
        return _node(node.body)
    if isinstance(node, ast.Constant):
        return E.const(_number(node.value))
    if isinstance(node, ast.Name):
        head, index = node.id[0], node.id[1:]
        if head in "ps" and index.isdigit():
            return E.param(int(index)) if head == "p" else E.slot(int(index))
        raise ValueError(f"unknown name {node.id!r}")
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = node.operand
        if isinstance(inner, ast.Constant):
            return E.const(-_number(inner.value))
        return ["neg", _node(inner)]
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return [_OPS[type(node.op)], _node(node.left), _node(node.right)]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        name = node.func.id
        args = [_node(arg) for arg in node.args]
        if name in ("min", "max") and len(args) >= 2:
            out = args[0]
            for arg in args[1:]:
                out = [name, out, arg]
            return out
        if name == "abs" and len(args) == 1:
            return ["abs", args[0]]
        if name in ("ifgt", "ifge") and len(args) == 3:
            return [name, *args]
    raise ValueError(f"unsupported syntax: {ast.dump(node)}")


def X(text: str) -> Expr:
    """Parse ``text`` (Python infix over pN / sK) into the expression language."""

    return _node(ast.parse(text, mode="eval"))


def _atom(node: ast.AST) -> tuple[Expr, str]:
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in _CMP:
        left, right = _node(node.left), _node(node.comparators[0])
        return ["-", left, right], _CMP[type(node.ops[0])]
    # A bare Boolean slot or flag: true is 1, so "holds" means "> 0".
    return _node(node), ">"


def condition(text: str) -> tuple[list[tuple[Expr, str]], str]:
    """``a >= b and c > d`` -> ([(a - b, '>='), (c - d, '>')], 'and')."""

    tree = ast.parse(text, mode="eval").body
    if isinstance(tree, ast.BoolOp):
        mode = "and" if isinstance(tree.op, ast.And) else "or"
        return [_atom(value) for value in tree.values], mode
    return [_atom(tree)], "or"


@dataclass(frozen=True)
class Decision:
    """An enum component: ``(condition, label)`` rules, first match wins."""

    rules: tuple[tuple[str, str], ...]
    default: str

    def to_decision_list(self):
        from .derive import DecisionList

        compiled = []
        for text, label in self.rules:
            atoms, mode = condition(text)
            compiled.append((atoms, mode, label))
        return DecisionList(rules=compiled, default=self.default)


def D(*rules: tuple[str, str], default: str) -> Decision:
    return Decision(tuple(rules), default)


def TF(text: str) -> Decision:
    """The Boolean enum ``true`` exactly when ``text`` holds."""

    return D((text, "true"), default="false")


#: A component whose reference value is the text rule's own reading of the
#: question (``textrules.run``): the KYC templates whose deciding input is a
#: word ("traceability is low"), which no numeric program can see.
TEXT = "@text"

Component = Union[str, Decision, None]


@dataclass(frozen=True)
class Reference:
    template_id: str
    slots: tuple[Component, ...]
    final: Component
    note: str = ""
    source: str = "question text"

    def slot_forms(self) -> dict[int, Component]:
        return {i: c for i, c in enumerate(self.slots) if c is not None}


def _places_of(spec: Any) -> int | None:
    rounding = (spec.get("rounding") or {}) if spec else {}
    if rounding.get("mode") == "half_up":
        return int(rounding["decimal_places"])
    return None


def reference_solver(form: Any, incumbent: Any, instances: Sequence[Any]) -> tuple[Any, list[str]]:
    """A solver carrying ``form`` over ``incumbent``'s slot layout.

    Accepts a :class:`Reference` or a :class:`genforms.TemplateForm`.  Returns
    the solver and the ids of the components the form defines; components it
    leaves out keep the incumbent's program, so later slots can still read
    them.  The caller contract-tests the result.
    """

    from .derive import SlotSolver, TemplateSolver

    if not isinstance(form, Reference):
        from . import genforms

        candidate = genforms.candidate_solver(form, incumbent, instances)
        defined = [
            incumbent.slots[p].slot_id for p in sorted(form.slots) if p < len(incumbent.slots)
        ]
        if form.final is not None and incumbent.final_kind != "enum":
            defined.append("final")
        return candidate, defined

    first = instances[0]
    if len(form.slots) != len(incumbent.slots):
        raise ValueError(
            f"{form.template_id}: {len(form.slots)} slot forms for "
            f"{len(incumbent.slots)} slots"
        )
    slot_specs = first.slot_specs
    candidate = TemplateSolver(
        template_id=incumbent.template_id,
        n_params=incumbent.n_params,
        final_kind=incumbent.final_kind,
        final_expression=incumbent.final_expression,
        final_places=incumbent.final_places,
        final_decision=incumbent.final_decision,
        source="reference-form",
        text_rules=incumbent.text_rules,
    )
    defined: list[str] = []
    for position, slot in enumerate(incumbent.slots):
        proposed = form.slots[position]
        if proposed is None:
            candidate.slots.append(
                SlotSolver(slot_id=slot.slot_id, kind=slot.kind, expression=slot.expression,
                           places=slot.places, decision=slot.decision)
            )
            continue
        defined.append(slot.slot_id)
        if proposed == TEXT:
            candidate.slots.append(SlotSolver(slot_id=slot.slot_id, kind="unsolved"))
            continue
        if isinstance(proposed, Decision):
            candidate.slots.append(
                SlotSolver(slot_id=slot.slot_id, kind="enum",
                           decision=proposed.to_decision_list())
            )
            continue
        places = _places_of(slot_specs[position])
        candidate.slots.append(
            SlotSolver(slot_id=slot.slot_id, kind="half_up" if places is not None else "exact",
                       expression=X(proposed), places=places)
        )
    if form.final is not None:
        defined.append("final")
        if form.final == TEXT:
            candidate.final_expression = None
            candidate.final_decision = None
        elif isinstance(form.final, Decision):
            candidate.final_kind = "enum"
            candidate.final_expression = None
            candidate.final_places = None
            candidate.final_decision = form.final.to_decision_list()
        else:
            candidate.final_kind = "decimal"
            candidate.final_expression = X(form.final)
            candidate.final_places = _places_of(first.answer_spec)
            candidate.final_decision = None
    return candidate, defined


def R(template_id: str, slots: Sequence[Component], final: Component, note: str = "") -> Reference:
    return Reference(template_id, tuple(slots), final, note)


def _npv(cash: Sequence[str], rate: str, start: int = 1) -> str:
    return " + ".join(f"{cf} / (1 + {rate}/100)**{t}" for t, cf in enumerate(cash, start=start))


# --------------------------------------------------------------------------
# the registry
# --------------------------------------------------------------------------

_ALL: list[Reference] = [
    # --- accounting_and_financial_reporting --------------------------------
    R("fp.accounting_and_financial_reporting.balance_sheets.business_combination.advanced.v1",
      ["p0 + p1*p2", "p3 + p4 + p5", "s1 - p6 - p7"], "s0 - s2",
      "consideration = cash + shares*price; goodwill = consideration - (assets - liabilities)"),
    R("fp.accounting_and_financial_reporting.balance_sheets.current_ratio_with_adjustment.intermediate.v1",
      ["p0 / p1", "p1 + p3", "p0 / s1"], "s0 - s2"),
    R("fp.accounting_and_financial_reporting.cash_flow_statements.closing_cash_balance.basic.v1",
      [], "p0 + p1 + p2 + p3"),
    R("fp.accounting_and_financial_reporting.cash_flow_statements.financing_activities.intermediate.v1",
      ["p0 + p1", "p2 + p3"], "s0 - s1"),
    R("fp.accounting_and_financial_reporting.cash_flow_statements.indirect_cash_flow_operations.intermediate.v1",
      ["p1 + p2", "-p3 - p4 - p5 + p6"], "p0 + s0 + s1",
      "AR and inventory increases and the AP decrease are uses of cash; accrued increase is a source"),
    R("fp.accounting_and_financial_reporting.cash_flow_statements.tax_cash_outflow.basic.v1",
      ["p2 - p1"], "p0 - s0"),
    R("fp.accounting_and_financial_reporting.depreciation_and_amortization.impairment_with_value_in_use.intermediate.v1",
      ["p0 - p1", "max(p2, p3)"], "max(0, s0 - s1)"),
    R("fp.accounting_and_financial_reporting.depreciation_and_amortization.straight_line_depreciation.basic.v1",
      ["p0 - p1"], "s0 / p2"),
    R("fp.accounting_and_financial_reporting.depreciation_and_amortization.sum_of_years_digits.basic.v1",
      ["p1 * (p1 + 1) / 2", "(p1 - p2 + 1) / s0"], "p0 * s1"),
    # --- corporate_finance --------------------------------------------------
    R("fp.corporate_finance.capital_structure.debt_to_equity_after_asset_sale.intermediate.v1",
      ["p2 - p3", "max(p0 - s0, 0)"], "s1 / p1"),
    R("fp.corporate_finance.capital_structure.debt_to_equity_after_buyback.basic.v1",
      ["p1 - p2"], "p0 / s0"),
    R("fp.corporate_finance.capital_structure.debt_to_equity_aggregate_debt.basic.v1",
      ["p0 + p1"], "s0 / p2"),
    R("fp.corporate_finance.capital_structure.debt_to_equity_bond_and_buyback.intermediate.v1",
      ["p0 + p2", "p1 - p3"], "s0 / s1"),
    R("fp.corporate_finance.capital_structure.debt_to_equity_bond_repay_buyback.advanced.v1",
      ["p0 + p2", "s0 - p3"], "s1 / (p1 - p4)"),
    R("fp.corporate_finance.div_policies.dividend_lintner_smoothing.intermediate.v1",
      ["p0 * p1/100", "p2 + p3/100 * (s0 - p2)"], "s1 * p4"),
    R("fp.corporate_finance.div_policies.dividend_stock_plus_growth.intermediate.v1",
      ["p0 * (1 + p1/100)", "p2 * (1 + p3/100)"], "s0 * s1"),
    R("fp.corporate_finance.eps.eps_pref_div_split_weighted.advanced.v1",
      ["p1 * p2 * 4", "p3 * p4"], "(p0 - s0) / s1",
      "adjusted shares = beginning shares * split factor; the split factor is 2 in every labelled draw"),
    R("fp.corporate_finance.eps.eps_pref_div_weighted.intermediate.v1",
      ["p0 - p1", "p2 + p3 * p4 / 12"], "s0 / s1"),
    R("fp.corporate_finance.eps.eps_quarterly_pref_buyback.intermediate.v1",
      ["p2 * p3 * 4", "p4 - p5 * p6 / 365"], "(p1 - s0) / s1"),
    R("fp.corporate_finance.eps.eps_quarterly_pref_div.basic.v1",
      ["p1 * p2 * 4", "p0 - s0"], "s1 / p3"),
    R("fp.corporate_finance.eps.eps_weighted_average.basic.v1",
      ["p3 / 12", "p1 + p2 * s0"], "p0 / s1"),
    # --- crypto_finance -----------------------------------------------------
    R("fp.crypto_finance.defi.liquidity_pool_reward.intermediate.v1",
      ["1 - p1/100", "p0 * s0"], "s1 * p2/100",
      "reward = distributable fees * provider share (p2), not the reserve rate (p1)"),
    R("fp.crypto_finance.defi.multi_factor_portfolio.advanced.v1",
      ["p0 * p1/100 * p2/100", "p0 * p3/100"], "s0 + s1",
      "staking impact = value * staking share * yield boost; the boost is 10 in every labelled draw"),
    R("fp.crypto_finance.global_events_impact.global_macro_strategy.advanced.v1",
      ["p1 + p2 + p3", "min(max(s0, p4), p5)", "1 + s1/100"], "p0 * s2",
      "sum all three impacts, clip to [floor, cap]"),
    R("fp.crypto_finance.global_events_impact.market_sentiment_shift.intermediate.v1",
      ["p1 / 100", "p0 * (1 + s0)"], "max(s1, p2)"),
    R("fp.crypto_finance.regulations.multi_factor_regulatory_risk.advanced.v1",
      ["p1 + p2 + p3", "p0 * s0 / 100", "s1 - p4"], "max(s2, 0)"),
    R("fp.crypto_finance.regulations.trade_cost_adjustment.intermediate.v1",
      ["p1 - 1", "p0 * s0"], "max(s1, p2)"),
    R("fp.crypto_finance.sentiments.multi_factor_sentiment.advanced.v1",
      ["p0 * p3", "p1 * p4", "s0 + s1 + p2 * p5"], "min(max(s2, p6), p7)",
      "weighted components; the labelled draws have weights 1 and zero news/price signals"),
    R("fp.crypto_finance.tokenomics.multi_factor_tokenomics.advanced.v1",
      ["p0 * (1 - p2/100)", "s0 * (1 + p3/100)", "p1 * (1 + p4/100)"], "s1 * s2",
      "emission (p3) grows the post-burn supply; market cap = supply * price, unclamped"),
    R("fp.crypto_finance.tokenomics.staking_reward_effect.intermediate.v1",
      ["p0 * (1 - p2/100)", "p1 * (1 + p3/100)"], "s0 * s1"),
    R("fp.crypto_finance.transaction_analysis.bulk_transaction_fees.intermediate.v1",
      ["p0 * (1 - p3/100)", "p1 * (1 - p4/100)", "p2 * (1 - p5/100)"], "s0 + s1 + s2"),
    R("fp.crypto_finance.transaction_analysis.multi_factor_transaction.advanced.v1",
      ["p0 * p1/100 * (1 - p5/100)", "p0 * (1 - p1/100) - p7", "s1 * (1 + p8/100)"], "s0 + s2",
      "p1 split to network 1, p5 its fee, p7 network 2 fixed fee, p8 its bonus"),
    R("fp.crypto_finance.whale_detection.cross_exchange_impact.advanced.v1",
      ["p0 * (1 - p1/100)", "s0 * (1 - p2/100)", "s1 - p3"], "max(s2, 0)"),
    # --- finance_regulation -------------------------------------------------
    R("fp.finance_regulation.aml.beneficial_ownership.intermediate.v1",
      ["p0 + p1", TF("s0 >= p2")], TF("s0 >= p2 or p3 > 0"),
      "p3 is the scenario control flag (the first true/false token)"),
    R("fp.finance_regulation.aml.multi_entity_ownership.intermediate.v1",
      ["p0 + p1 + p2", "max(p0, p1, p2)"], TF("s0 >= p3 or s1 >= p4")),
    R("fp.finance_regulation.aml.structuring_detection.basic.v1",
      [TF("p0 >= p2"), TF("p1 < p3")], TF("s0 > 0 and s1 > 0"),
      "count at or above the trigger; amount strictly below the ceiling"),
    R("fp.finance_regulation.basel.multi_requirement.advanced.v1",
      [TF("100 * p1 >= p7 * p2"), TF("100 * p3 >= p8 * p4"), TF("100 * p5 >= p9 * p6")],
      TF("s0 > 0 and s1 > 0 and s2 > 0"),
      "leverage T1/exposure >= 3%, capital total/RWA >= 10.5%, liquidity >= 100% of outflows"),
    R("fp.finance_regulation.security.multiple_reporting_thresholds.intermediate.v1",
      [TF("p0 >= p2"), TF("p1 >= p3")], TF("s0 > 0 or s1 > 0")),
    # --- financial_markets --------------------------------------------------
    R("fp.financial_markets.bond_pricing.dirty_price_with_simple_accrual.advanced.v1",
      ["p1 * p2 / 100", "s0 / p3", "s1 * p4 / p5"], "p0 + s2"),
    R("fp.financial_markets.bond_pricing.two_year_par_bond_ytm.intermediate.v1",
      ["p0 * p1 / 100", "s0 / p0"], "s1 * 100"),
    R("fp.financial_markets.forex_trading.eur_to_gbp_cross_conversion.intermediate.v1",
      ["p1 / p2"], "p0 * s0",
      "cross rate = (USD per EUR)/(USD per GBP); it is 2 in every labelled draw"),
    R("fp.financial_markets.forex_trading.foreign_to_usd_conversion.basic.v1",
      [], "p0 * p1"),
    R("fp.financial_markets.forex_trading.long_position_profit_loss.intermediate.v1",
      ["p2 - p1", "s0 / p3", "p3 * p0"], "s1 * s2"),
    R("fp.financial_markets.option_pricing.factorized_call_value.advanced.v1",
      ["p0 * p3", "p1 * p6", "s1 * p5"], "s0 - s2"),
    R("fp.financial_markets.option_pricing.long_call_roi.intermediate.v1",
      ["max(p2 - p1, 0)", "s0 - p0"], "s1 / p0 * 100",
      "ROI percent multiplies by 100, not by the strike (which is 100 in every labelled draw)"),
    R("fp.financial_markets.stock_market_analysis.share_price_from_pe.intermediate.v1",
      ["p1 / p2"], "p0 * s0"),
    R("fp.financial_markets.stock_market_analysis.simple_capital_gain.basic.v1",
      ["p0 * p1", "p0 * p2"], "s1 - s0"),
    R("fp.financial_markets.stock_market_analysis.stock_total_dollar_return.intermediate.v1",
      ["p0 * p1", "p0 * p2", "p0 * p3"], "s2 + s1 - s0"),
    R("fp.financial_markets.stock_market_analysis.two_lot_sale_net_profit.advanced.v1",
      ["p0 + p2", "(p0*p1 + p2*p3) / s0", "p4 * s0"], "s2 - (p0*p1 + p2*p3)",
      "average cost is the exact lot-weighted mean; the lot prices differ by 10 in every labelled draw"),
    # --- financial_ratios ---------------------------------------------------
    R("fp.financial_ratios.effratio.asset_turnover_average_assets.intermediate.v1",
      ["(p1 + p2) / 2"], "p0 / s0"),
    R("fp.financial_ratios.effratio.asset_turnover_compare_periods.basic.v1",
      ["p0 / p1", "p0 / (p1 + p2)"], "s0 - s1",
      "prior turnover = sales / prior assets; it is exactly 1/2 in every labelled draw"),
    R("fp.financial_ratios.effratio.asset_turnover_with_depreciation.intermediate.v1",
      ["p0 / p1", "p1 - p2", "p0 / s1"], "s2 - s0"),
    R("fp.financial_ratios.effratio.investment_vs_sales_push.advanced.v1",
      ["p0 / (p1 + p3 - p4)", "p0 * (1 + p6/100) / p1"], "s1 - s0"),
    R("fp.financial_ratios.levratio.capital_injection.intermediate.v1",
      ["p1 + p2"], "p0 / s0"),
    R("fp.financial_ratios.levratio.convertible_debt.basic.v1",
      ["p0 - p2", "p1 + p2"], "s0 / s1"),
    R("fp.financial_ratios.levratio.debt_repayment_and_borrowing.intermediate.v1",
      ["p0 - p2", "s0 + p3"], "s1 / p1"),
    R("fp.financial_ratios.levratio.debt_vs_equity_scenarios.advanced.v1",
      ["(p0 + p2) / p1", "p0 / (p1 + p3)"], "s0 - s1"),
    R("fp.financial_ratios.liqratio.both_ratios.intermediate.v1",
      ["p0 / p3", "p0 - p1 - p2"], "s1 / p3"),
    R("fp.financial_ratios.liqratio.liquidity_minimum_quick_ratio.advanced.v1",
      ["(p0 + p1 + p2 + p3 + p4) / p5", "(p0 + p1 + p2) / p5", "p5 * p6"],
      "max(s2 - (p0 + p1 + p2), 0)",
      "securities + inventory = receivables in every labelled draw"),
    R("fp.financial_ratios.liqratio.quick_ratio_simple.basic.v1",
      ["p0 - p1"], "s0 / p2"),
    R("fp.financial_ratios.liqratio.quick_ratio_target.intermediate.v1",
      ["p0 - p1 - p2", "p3 * p4"], "max(s1 - s0, 0)",
      "inventory = CA/5 and prepaid = CA/20 in every labelled draw"),
    # --- fintech ------------------------------------------------------------
    R("fp.fintech.digital_banking.extra_payment_payoff.advanced.v1",
      ["p1 * p2", "max(p0 - s0, 0)", "max(s1 - p3, 0)"], "s2 / p1"),
    R("fp.fintech.payment_technologies.batch_effective_fee.intermediate.v1",
      ["p1 * p2", "p0 * p3/100", "s0 + s1"], "s2 / p0 * 100"),
    R("fp.fintech.payment_technologies.cross_border_net.intermediate.v1",
      ["p1 * (1 - p2/100)", "p0 * s0"], "s1 - p3"),
    R("fp.fintech.payment_technologies.effective_monthly_fee.advanced.v1",
      ["p0 * p1", "max(s0 - p5, 0)", "p2 + p3*p0 + p4/100 * min(s0, p5) + p6/100 * s1"],
      "s2 / s0 * 100"),
    R("fp.fintech.robo_advisors.equity_rebalance_trade.intermediate.v1",
      ["p0 + p1", "s0 * p2/100"], "s1 - p0"),
    R("fp.fintech.robo_advisors.tax_loss_savings.advanced.v1",
      ["max(p1 - p2, 0)", "p0 * s0", "p3 / 100"], "s1 * s2"),
    # --- investment_analysis ------------------------------------------------
    R("fp.investment_analysis.ci.midterm_deposit_compound_interest.advanced.v1",
      ["p0 * (1 + p3/100)**(p1 + p4)", "p2 * (1 + p3/100)**p4", "s0 + s1"], "s2 - p0 - p2"),
    R("fp.investment_analysis.npv.four_year_annuity_salvage_npv.intermediate.v1",
      ["p1 + p2", "s0 / (1 + p3/100)**4", _npv(["p1", "p1", "p1"], "p3") + " + s1"], "s2 - p0"),
    R("fp.investment_analysis.npv.four_year_cleanup_npv.advanced.v1",
      [_npv(["p1", "p2", "p3", "p4"], "p6"), "p5 / (1 + p6/100)**4", "s0 - p0"], "s2 - s1"),
    R("fp.investment_analysis.npv.single_year_npv.basic.v1",
      ["p1 / (1 + p2/100)", "1 + p2/100"], "s0 - p0"),
    R("fp.investment_analysis.npv.three_year_salvage_npv.intermediate.v1",
      ["p3 + p4", "s0 / (1 + p5/100)**3", _npv(["p1", "p2"], "p5") + " + s1"], "s2 - p0"),
    R("fp.investment_analysis.npv.two_year_npv.basic.v1",
      ["p1 / (1 + p3/100)", "p2 / (1 + p3/100)**2", "s0 + s1"], "s2 - p0"),
    R("fp.investment_analysis.rar.three_asset_capm_portfolio.advanced.v1",
      ["p0 + p2 + p4", "(p0*p1 + p2*p3 + p4*p5) / s0", "p7 - p6"], "p6 + s1 * s2",
      "total value is the sum of the three holdings, which form an arithmetic progression in every labelled draw"),
    R("fp.investment_analysis.rar.two_asset_perfect_correlation_sd.basic.v1",
      ["p1/100 * p2", "p3/100 * p4", "(s0 + s1)**2"], "s0 + s1"),
    R("fp.investment_analysis.roi.after_tax_roi.basic.v1",
      ["1 - p2/100", "p1 * s0"], "s1 / p0 * 100"),
    R("fp.investment_analysis.roi.conversion_campaign_roi.intermediate.v1",
      ["p0 * p1/100", "s0 * p2/100", "s1 * p3"], "(s2 - p4) / p4 * 100"),
    R("fp.investment_analysis.roi.mutual_fund_total_roi.advanced.v1",
      ["p0 * p3 * p4", "p0 * p1 * p5/100 * p4", "p0*p2 - p0*p1 + s0 - s1"],
      "s2 / (p0 * p1) * 100"),
    R("fp.investment_analysis.roi.property_roi.basic.v1",
      ["p0 + p1", "p2 - s0"], "s1 / s0 * 100"),
    # --- mergers_and_acquisitions -------------------------------------------
    R("fp.mergers_and_acquisitions.deal_structure.control_premium_debt_earnout_calculation.advanced.v1",
      ["p0 * p1/100", "p0 + s0 + p2 * p3/100"], "s1 * (1 - p4/100)"),
    R("fp.mergers_and_acquisitions.due_diligence.due_diligence_after_tax_interest_cost.intermediate.v1",
      ["p0 * p1/100", "1 - p2/100"], "s0 * s1"),
    R("fp.mergers_and_acquisitions.due_diligence.due_diligence_synergy_estimation.intermediate.v1",
      ["p0 + p1", "s0 * p2/100"], "s1 - p3"),
    R("fp.mergers_and_acquisitions.post-merger_integration.integration_cost_reduction.intermediate.v1",
      ["p0 + p1", "s0 * p2/100"], "s1 - p3"),
    R("fp.mergers_and_acquisitions.post-merger_integration.integration_synergy_calculation.basic.v1",
      ["p0 + p1"], "s0 * p2/100"),
    R("fp.mergers_and_acquisitions.post-merger_integration.revenue_synergy_net_gain.intermediate.v1",
      ["p0 + p1", "s0 * p2/100"], "s1 - s0 * p3/100"),
    R("fp.mergers_and_acquisitions.post-merger_integration.supply_chain_npv_net_benefit.advanced.v1",
      ["(p0 + p1) * p2/100",
       "ifgt(p4, s0 * (1 - (1 + p4/100)**(-p3)) / (p4/100), s0 * p3)"],
      "s1 - p5",
      "sum of the annual saving discounted over years 1..horizon, in closed form; the "
      "question says the horizon is 3, 4 or 5, but a test draw discloses 12, and the "
      "recipe sums through the disclosed horizon whatever it is"),
    R("fp.mergers_and_acquisitions.post-merger_integration.valuation_adjustment_after_integration.basic.v1",
      ["p0 + p1", "1 + p2/100"], "s0 * s1"),
    R("fp.mergers_and_acquisitions.synergies_and_cost_savings.synergy_basic_cost_reduction.basic.v1",
      ["p0 + p1"], "s0 * p2/100",
      "savings = combined cost * rate; the first cost base is 10x the rate in every labelled draw"),
    R("fp.mergers_and_acquisitions.synergies_and_cost_savings.synergy_basic_fixed_savings.basic.v1",
      [], "p0 + p1"),
    R("fp.mergers_and_acquisitions.synergies_and_cost_savings.synergy_complex_after_tax.advanced.v1",
      ["(p0 + p1) * p2/100", "s0 - p3/p4"], "s1 * (1 - p5/100)"),
    R("fp.mergers_and_acquisitions.synergies_and_cost_savings.synergy_complex_multi_category.intermediate.v1",
      ["p0 + p1", "s0 * p2/100"], "s1 + p3"),
    R("fp.mergers_and_acquisitions.synergies_and_cost_savings.synergy_complex_net_savings.intermediate.v1",
      ["p0 + p1", "s0 * p2/100"], "s1 - p3"),
    R("fp.mergers_and_acquisitions.valuation_methods.comp_ebitda_multiple_with_net_debt.intermediate.v1",
      ["p0 * p1", "p2 - p3"], "s0 - s1"),
    R("fp.mergers_and_acquisitions.valuation_methods.comparable_revenue_valuation.basic.v1",
      ["p0 * p1"], "s0 - p2"),
    R("fp.mergers_and_acquisitions.valuation_methods.ebitda_multiple_valuation.basic.v1",
      ["p0 * p1"], "s0 - p2"),
    # --- personal_finance ---------------------------------------------------
    R("fp.personal_finance.personalinvest.diversification_risk.advanced.v1",
      ["p0*p2 + p1*p3", TF("p0 >= p5 or p1 >= p5"), "p4 * s1"], "s0 + s2",
      "concentration when the larger weight is at least the threshold, including equality"),
    R("fp.personal_finance.saveretire.early_retirement_bridge.advanced.v1",
      ["max(p1 - p3, 0)", "s0 * p2 * (1 + p4)", "s1 - p0"], TF("p0 >= s1")),
]

# Every other template, read the same way, so the audit covers all 290
# (``document_validity`` is omitted: it has no numeric component at all and
# its only reading is the text rule the solver already ships).
_A = "fp.accounting_and_financial_reporting."
_C = "fp.corporate_finance."
_K = "fp.crypto_finance."
_G = "fp.finance_regulation."
_M = "fp.financial_markets."
_Q = "fp.financial_ratios."
_F = "fp.fintech."
_I = "fp.investment_analysis."
_X = "fp.mergers_and_acquisitions."
_P = "fp.personal_finance."
_R = "fp.risk_management."
_S = "fp.sustainable_finance."

_REST: list[Reference] = [
    # accounting
    R(_A + "balance_sheets.balance_sheet_equation.basic.v1", [], "p0 - p1"),
    R(_A + "balance_sheets.cash_accounts_payable.basic.v1", [], "p0 - p1"),
    R(_A + "balance_sheets.inventory_turnover_days.intermediate.v1",
      ["p0 + p1 - p2", "(p0 + p2) / 2", "s0 / s1"], "365 / s2"),
    R(_A + "cash_flow_statements.acquisition_cash_flow_impact.advanced.v1",
      ["p1 + p2 + p3 + p4", "p0 + p5 + p6"], "s0 - s1"),
    R(_A + "depreciation_and_amortization.asset_impairment_reversal.advanced.v1",
      ["p1 - p0", "max(s0, 0)"], "min(p2, s1)"),
    R(_A + "depreciation_and_amortization.partial_year_disposal.intermediate.v1",
      ["p0 / p1", "s0 * (p2/12 + p3)", "p0 - s1"], "p4 - s2"),
    R(_A + "income_statements.depreciation_ddb.intermediate.v1",
      ["2 / p1", "p0 * (1 - s0)", "s1 * s0"], "s1 - s2"),
    R(_A + "income_statements.dta_warranty_expense.advanced.v1", ["p0 - p1", "p2 / 100"], "s0 * s1"),
    R(_A + "income_statements.inventory_turnover.intermediate.v1",
      ["(p2 + p3) / 2", "p1 / s0"], "365 / s1"),
    R(_A + "income_statements.operating_expenses_effect.basic.v1", [], "p0 - p1"),
    R(_A + "income_statements.revenue_vs_cogs.basic.v1", [], "p0 - p1"),
    # corporate finance
    R(_C + "div_policies.dividend_lintner_three_year_avg.advanced.v1",
      ["(p0 + p1 + p2) / 3", "p4 + p5/100 * (s0 * p3/100 - p4)"], "s1 * p6"),
    R(_C + "div_policies.dividend_stable_growth_policy.basic.v1", ["1 + p1/100", "p0 * s0"], "s1 * p2"),
    R(_C + "div_policies.dividend_target_payout_policy.basic.v1", ["p0 * p1/100"], "s0 * p2"),
    R(_C + "wacc.capm_wacc.basic.v1",
      ["p4 - p3", "p3 + p2 * s0", "p1 / (p0 + p1)"], "(1 - s2) * s1 + s2 * p5 * (1 - p6/100)"),
    R(_C + "wacc.preferred_capm_wacc.intermediate.v1",
      ["p4 + p3 * (p5 - p4)", "p1 / (p0 + p1 + p2)", "p7 * (1 - p8/100)"],
      "(p0 * s0 + p1 * p6 + p2 * s2) / (p0 + p1 + p2)"),
    R(_C + "wacc.standard_wacc.basic.v1",
      ["p0 + p1", "p0 / s0", "p3 * (1 - p4/100)"], "s1 * p2 + (1 - s1) * s2"),
    R(_C + "wacc.weighted_debt_wacc.intermediate.v1",
      ["p1 + p3", "(p1*p2 + p3*p4) / s0", "s0 / (p0 + s0)"], "(1 - s2) * p5 + s2 * s1 * (1 - p6/100)"),
    # crypto
    R(_K + "defi.staking_return.basic.v1", ["p1 / 100"], "p0 * s0"),
    R(_K + "defi.swap_fee.basic.v1", ["p1 / 100"], "p0 * s0"),
    R(_K + "defi.yield_farming_roi.intermediate.v1", ["p1 / 100", "p2 / 12"], "p0 * s0 * s1"),
    R(_K + "global_events_impact.crypto_price_drop.basic.v1", ["1 - p1/100"], "p0 * s0"),
    R(_K + "global_events_impact.crypto_volume_increase.basic.v1", ["1 + p1/100"], "p0 * s0"),
    R(_K + "global_events_impact.regulatory_event.intermediate.v1", ["p1 / 100", "s0 + 1"], "p0 * s1"),
    R(_K + "regulations.compliance_fee_adjustment.basic.v1", [], "p0 * p1"),
    R(_K + "regulations.crypto_tax_penalty.basic.v1", ["p1 / 100"], "p0 * s0"),
    R(_K + "regulations.regulatory_impact.intermediate.v1", ["p1 / 100", "p0 * s0"], "s1 + p2"),
    R(_K + "sentiments.news_impact.intermediate.v1", ["p1 * p2", "p3 / 100"], "p0 * s0 * s1"),
    R(_K + "sentiments.price_sentiment.basic.v1", [], "p0 * p1"),
    R(_K + "sentiments.tweet_influence.intermediate.v1", ["p2 / 100", "p0 * p1"], "s0 * s1"),
    R(_K + "sentiments.volume_sentiment.basic.v1", [], "p0 * p1"),
    R(_K + "tokenomics.emission_schedule_impact.intermediate.v1",
      ["p2 / 100", "p0 * (1 + s0)"], "s1 * p1"),
    R(_K + "tokenomics.market_cap_calculation.basic.v1", [], "p0 * p1"),
    R(_K + "tokenomics.token_price_calculation.basic.v1", [], "p0 / p1",
      "price = market cap / supply; it rounds to 0.00 on every labelled draw"),
    R(_K + "transaction_analysis.cross_chain_transfer.intermediate.v1",
      ["1 - p1/100", "p0 * s0"], "s1 + p2"),
    R(_K + "transaction_analysis.fixed_fee_transaction.basic.v1", [], "p0 - p1"),
    R(_K + "transaction_analysis.transaction_fee_calculation.basic.v1", ["1 - p1/100"], "p0 * s0"),
    R(_K + "whale_detection.large_transfer_detection.basic.v1", ["p0 - p1"], "max(s0, 0)"),
    R(_K + "whale_detection.multiple_transaction_analysis.intermediate.v1",
      ["max(p0 - p3, 0)", "max(p1 - p3, 0)", "max(p2 - p3, 0)"], "s0 + s1 + s2"),
    R(_K + "whale_detection.threshold_adjustment_detection.intermediate.v1",
      ["p1 * (1 + p2/100)", "p0 - s0"], "max(s1, 0)"),
    R(_K + "whale_detection.wallet_activity_detection.basic.v1", [], "p0 / p1"),
    # finance regulation
    R(_G + "aml.sar_decision.advanced.v1",
      [D(("p0 >= p3", "true"), ("p5 > 0 and p6 > 0", "true"), default="false"),
       TF("p0 >= p4 or p5 > 0 or p6 > 0")],
      D(("s0 > 0", "file_sar"), ("s1 > 0", "manual_review"), default="no_action")),
    R(_G + "aml.threshold_violation.basic.v1", ["p0 - p1"], TF("s0 >= 0")),
    R(_G + "basel.capital_buffer.intermediate.v1", ["p1 + p2"], "p0 * s0 / 100"),
    R(_G + "basel.leverage_ratio.basic.v1", ["p1 / p2 * 100"], TF("s0 >= p3")),
    R(_G + "basel.rwa_increase.intermediate.v1", ["p1 + p2", "p0 / s0 * 100"], TF("s1 >= p3")),
    R(_G + "basel.tier1_composition.basic.v1", ["p0 + p2", "s0 / p4"], "s1 * 100"),
    R(_G + "compliance.composite_risk.advanced.v1",
      ["p0 * (1 - p1)", "s0 + p2", TF("s1 >= p3 or p5 > 0")],
      D(("s2 > 0", "high_risk"), ("s1 >= p4", "medium_risk"), default="low_risk"),
      "p5 is the high-risk override flag"),
    R(_G + "compliance.delayed_fine.intermediate.v1", ["p1 * p2"], "p0 + s0"),
    R(_G + "compliance.fine_calculation.basic.v1", [], "p0 * p1"),
    R(_G + "compliance.regional_weighted_score.intermediate.v1", ["p0 * p2", "p1 * p3"], "s0 + s1"),
    R(_G + "compliance.risk_score.basic.v1", [], "p0 * p1"),
    R(_G + "kyc.country_sector_risk.intermediate.v1",
      ["p0 * p1", D(("s0 >= p2", "high_risk"), ("s0 >= p3", "medium_risk"), default="standard_risk")],
      D(("s0 >= p2 or p6 > 0", "high_risk"), ("s0 >= p3 or p7 > 0", "medium_risk"),
        default="standard_risk"),
      "p6 is the high-risk override flag, p7 the sector EDD flag"),
    R(_G + "kyc.customer_risk_rating.advanced.v1", [TEXT, TEXT, TEXT],
      D(("s2 >= p19", "high_risk"), ("s2 <= p16", "low_risk"), default="medium_risk")),
    R(_G + "kyc.customer_type.basic.v1",
      [TEXT, D(("p0 > 1", "multiple_holders"), default="single_holder")], TEXT),
    R(_G + "kyc.source_of_funds.intermediate.v1", ["p0 + p1", TEXT], TEXT,
      "the route turns on the word giving evidence traceability; only the text rule reads it"),
    R(_G + "security.disclosure_threshold.basic.v1", ["p0 - p1"], TF("s0 >= 0")),
    R(_G + "security.merger_timing.advanced.v1", ["p1 - p0", TF("s0 > p2")],
      D(("p3 > 0", "immediate_escalation"), ("s1 > 0", "late_disclosure"),
        default="timely_disclosure")),
    R(_G + "security.offer_investment_limit.intermediate.v1",
      ["max(p0, p1)", "s0 * p3 / 100"], TF("p2 <= s1")),
    R(_G + "security.trading_gain.basic.v1", ["p2 - p1"], "p0 * s0"),
    # financial markets
    R(_M + "bond_pricing.one_year_coupon_bond_price.basic.v1",
      ["p0 * p1/100", "p0 + s0"], "s1 / (1 + p2/100)"),
    R(_M + "bond_pricing.three_year_coupon_bond_price.intermediate.v1",
      ["p0 * p1/100", "p0 + s0", "s1 / (1 + p2/100)**3"],
      "s0 / (1 + p2/100) + s0 / (1 + p2/100)**2 + s2"),
    R(_M + "bond_pricing.zero_coupon_bond_price.basic.v1", ["(1 + p2/100)**p1"], "p0 / s0"),
    R(_M + "forex_trading.triangular_arbitrage_profit.advanced.v1",
      ["p0 * p1", "s0 * p2", "s1 * p3"], "s2 - p0"),
    R(_M + "forex_trading.usd_quote_pip_value.basic.v1", [], "p0 * p1"),
    R(_M + "option_pricing.call_intrinsic_value.basic.v1", ["p0 - p1"], "max(s0, 0)"),
    R(_M + "option_pricing.put_intrinsic_value.basic.v1", ["p1 - p0"], "max(s0, 0)"),
    R(_M + "stock_market_analysis.dividend_yield.basic.v1", ["p0 / p1"], "s0 * 100"),
    # financial ratios
    R(_Q + "effratio.asset_turnover_simple.basic.v1", [], "p0 / p1"),
    R(_Q + "levratio.debt_to_equity_simple.basic.v1", [], "p0 / p1"),
    R(_Q + "liqratio.current_ratio_simple.basic.v1", [], "p0 / p1"),
    R(_Q + "profitratio.dual_margin_gap.intermediate.v1",
      ["(p0 - p1) / p0 * 100", "p2 / p0 * 100"], "s0 - s1"),
    R(_Q + "profitratio.gross_profit_margin.basic.v1", ["p0 - p1", "s0 / p0"], "s1 * 100"),
    R(_Q + "profitratio.net_profit_margin.basic.v1", ["p1 / p0"], "s0 * 100"),
    R(_Q + "profitratio.operating_margin.intermediate.v1", ["p0 - p1", "s0 - p2"], "s1 / p0 * 100"),
    R(_Q + "profitratio.target_net_margin.advanced.v1",
      ["p1 / p0 * 100", "p0 * p2/100"], "max(s1 - p1, 0)"),
    # fintech
    R(_F + "digital_banking.highest_spend_amount.intermediate.v1", ["max(p0, p1)"], "max(s0, p2)"),
    R(_F + "digital_banking.monthly_deposit_future_value.intermediate.v1",
      ["p2 / 100", "(1 + s0)**p1", "(s1 - 1) / s0"], "p0 * s2"),
    R(_F + "digital_banking.simple_interest_balance.basic.v1", ["p0 * p1/100 * p2"], "p0 + s0"),
    R(_F + "digital_banking.transfer_total_deduction.basic.v1", ["p0 * p1/100"], "p0 + s0"),
    R(_F + "payment_technologies.bnpl_installment.basic.v1", ["p1 / 100", "p0 * (1 + s0)"], "s1 / p2"),
    R(_F + "payment_technologies.card_processing_net.basic.v1", ["1 - p1/100"], "p0 * s0"),
    R(_F + "robo_advisors.monthly_contribution_projection.intermediate.v1",
      ["(1 + p2/100)**p1", "(s0 - 1) / (p2/100)", "p0 * s1"], "s2 * (1 - p3/100)"),
    R(_F + "robo_advisors.net_portfolio_after_fee.basic.v1", ["1 - p1/100"], "p0 * s0"),
    R(_F + "robo_advisors.one_year_after_fee.basic.v1",
      ["1 + p1/100", "p0 * s0"], "s1 * (1 - p2/100)"),
    # investment analysis
    R(_I + "ci.interest_from_known_total.intermediate.v1",
      ["(1 + p2/100)**p1", "p0 / s0"], "p0 - s1"),
    R(_I + "ci.quarterly_compound_interest.basic.v1",
      ["p1/100 / p3", "p0 * (1 + s0)**(p3 * p2)"], "s1 - p0"),
    R(_I + "ci.simple_annual_compound_interest.basic.v1",
      ["p0 * (1 + p1/100)**p2", "s0 / p0"], "s0 - p0"),
    R(_I + "ci.two_phase_semiannual_interest.intermediate.v1",
      ["(1 + p2/100/2)**(2*p1)", "(1 + p4/100/2)**(2*p3)", "p0 * s0 * s1"], "s2 - p0"),
    R(_I + "irr.after_tax_net_sale_cost.intermediate.v1",
      ["p2 - p3", "max(s0 - p0, 0)", "s0 - p4/100 * s1"], "(s2 / p0 - 1) * 100",
      "tax applies only to a strictly positive net gain"),
    R(_I + "irr.after_tax_sale.basic.v1",
      ["max(p2 - p0, 0)", "p3/100 * s0", "p2 - s1"], "(s2 / p0 - 1) * 100"),
    R(_I + "irr.bond_coupon_reinvestment.intermediate.v1",
      ["p2 * p3/100 / 2", "s0 * (1 + p4/100 / 2)", "p2 + s0 + s1"], "(s2 / p0 - 1) * 100"),
    R(_I + "irr.net_sale_proceeds.basic.v1", ["p2 - p3", "s0 / p0"], "(s1 - 1) * 100"),
    R(_I + "irr.six_month_after_tax_net_sale.advanced.v1",
      ["p2 - p3", "s0 - p4/100 * max(s0 - p0, 0)", "s1 / p0"], "(s2**2 - 1) * 100"),
    R(_I + "rar.jensen_alpha.intermediate.v1", ["p2 - p1", "p1 + p3 * s0"], "p0 - s1"),
    R(_I + "rar.m_squared_measure.intermediate.v1",
      ["p0 - p2", "s0 / p1", "s1 * p3"], "p2 + s2"),
    R(_I + "rar.sharpe_ratio.basic.v1", ["p0 - p1"], "s0 / p2"),
    R(_I + "roi.compound_growth_roi.intermediate.v1",
      ["(1 + p1/100)**p2", "p0 * s0", "s1 - p0"], "s2 / p0 * 100"),
    # mergers and acquisitions
    R(_X + "deal_structure.cash_payment_calculation.basic.v1", ["p1 / 100"], "p0 * s0"),
    R(_X + "deal_structure.stock_swap_calculation.basic.v1", [], "p0 / p1"),
    R(_X + "due_diligence.due_diligence_pe_valuation.basic.v1", [], "p0 * p1"),
    R(_X + "due_diligence.due_diligence_working_capital.basic.v1", [], "p0 - p1"),
    # personal finance
    R(_P + "budgeting.cost_reallocation.basic.v1", ["p1 - p2"], "p0 + s0"),
    R(_P + "budgeting.cut_reforecast.intermediate.v1", ["p0 * p1"], "p0 - s0 + p2"),
    R(_P + "budgeting.long_term_growth.advanced.v1", ["1 + p1", "s0**p2"], "p0 * s1"),
    R(_P + "budgeting.project_adjustment.intermediate.v1", ["p1 * p2", "p1 + s0"], "p0 + s1"),
    R(_P + "budgeting.simple_allocation.basic.v1", [], "p0 * p1"),
    R(_P + "loanrepay.early_payoff.advanced.v1",
      ["ifgt(p4, 0, p0 * p2)", "p0 + p1 + s0", "p3 - s1"], TF("s2 >= 0"),
      "p4 is the penalty-waived flag"),
    R(_P + "loanrepay.extra_payment_total.intermediate.v1", ["p0 + p1"], "s0 * p2"),
    R(_P + "loanrepay.monthly_installment.basic.v1", [], "p0 / p1"),
    R(_P + "loanrepay.refinance_benefit.intermediate.v1", ["p0 - p1"], "s0 - p2"),
    R(_P + "loanrepay.simple_repayment.basic.v1", [], "p0 + p1"),
    R(_P + "personalinvest.compound_growth.basic.v1", ["1 + p1", "s0**p2"], "p0 * s1"),
    R(_P + "personalinvest.portfolio_allocation.basic.v1", ["p0 * (1 - p1)"], "p0 * p1"),
    R(_P + "personalinvest.volatility_band.intermediate.v1", ["p0 * p1", "p0 - s0"], "p0 + s0"),
    R(_P + "personalinvest.withdrawal_balance.intermediate.v1", ["p1 * p2", "p1 + s0"], "p0 - s1"),
    R(_P + "saveretire.additional_saving.basic.v1",
      ["p1 + p2 * p3", "max(p0 - s0, 0)"], "s1 / p3"),
    R(_P + "saveretire.inflation_adjustment.intermediate.v1", ["1 + p1", "s0**p2"], "p0 * s1"),
    R(_P + "saveretire.one_period_growth.intermediate.v1", ["p0 + p1", "s0 * p2"], "s0 + s1"),
    R(_P + "saveretire.years_to_target.basic.v1", ["max(p0 - p1, 0)"], "s0 / p2"),
    R(_P + "taxcalc.capital_gains.intermediate.v1", ["max(p0 - p1, 0)"], "s0 * p2"),
    R(_P + "taxcalc.flat_tax.basic.v1", [], "p0 * p1"),
    R(_P + "taxcalc.foreign_tax_relief.advanced.v1",
      ["p0 * p1", "min(p2, s0 * p3)"], "max(s0 - s1, 0)"),
    R(_P + "taxcalc.itemized_deduction.intermediate.v1",
      ["max(p1, p2)", "max(p0 - s0, 0)"], "s1 * p3"),
    R(_P + "taxcalc.standard_deduction.basic.v1", ["max(p0 - p1, 0)"], "s0 * p2"),
    # risk management
    R(_R + "regulatory_compliance.capital_requirement.intermediate.v1", ["p1 - p0"], "max(s0, 0)"),
    R(_R + "regulatory_compliance.capital_shortfall.basic.v1", ["p1 - p0"], "max(s0, 0)"),
    R(_R + "regulatory_compliance.compliance_penalty.basic.v1",
      ["p0 - p1", "max(s0, 0)"], "s1 * p2/100"),
    R(_R + "regulatory_compliance.liquidity_gap.intermediate.v1", ["p1 - p0"], "max(s0, 0)"),
    R(_R + "regulatory_compliance.multi_factor_regulatory_compliance.advanced.v1",
      ["max(p0 - p1, 0) * p2/100", "max(p4 - p3, 0)", "max(p6 - p5, 0)"], "s0 + s1 + s2"),
    R(_R + "risk_appetite.capital_allocation_risk_appetite.basic.v1", ["p1 / 100"], "p0 * s0"),
    R(_R + "risk_appetite.multi_factor_risk_appetite_assessment.advanced.v1",
      ["p1 / 100", "1 + p2/100"], "p0 * s0 * s1"),
    R(_R + "risk_appetite.risk_adjusted_return.intermediate.v1",
      ["p1 / 100", "p2 / 100"], "p0 * s0 * s1"),
    R(_R + "risk_appetite.risk_exposure_limit.intermediate.v1", ["p1 / 100"], "p0 * s0"),
    R(_R + "risk_appetite.risk_threshold_measurement.basic.v1", ["p1 / 100"], "p0 * s0"),
    R(_R + "risk_metrics.liquidity_risk.intermediate.v1", ["p1 / 100"], "p0 * s0"),
    R(_R + "risk_metrics.multi_factor_portfolio.advanced.v1",
      ["p0 * p2/100 * p9/100 * p15", "p0 * p4/100 * p11/100 * p17", "p0 * p6/100 * p13/100 * p19"],
      "s0 + s1 + s2"),
    R(_R + "risk_metrics.portfolio_var.basic.v1", ["p1 / 100"], "p0 * s0 * p2"),
    R(_R + "risk_metrics.stock_sensitivity.basic.v1", ["p1 / 100"], "p0 * s0"),
    R(_R + "risk_metrics.volatility_sensitivity.intermediate.v1", [], "p0 * p1"),
    R(_R + "scenario_planning.interest_rate_impact.intermediate.v1", ["p1 / 100"], "p0 * s0 * p2"),
    R(_R + "scenario_planning.investment_scenario_planning.advanced.v1",
      ["p4 * p1 / 100", "p5 * p2 / 100", "p6 * p3 / 100"], "p0 * (s0 + s1 + s2)"),
    R(_R + "scenario_planning.market_downturn_revenue.basic.v1", ["1 - p1/100"], "p0 * s0"),
    R(_R + "scenario_planning.operating_cost_increase.basic.v1", ["1 + p1/100"], "p0 * s0"),
    R(_R + "scenario_planning.revenue_recovery_effect.intermediate.v1",
      ["1 - p1/100", "1 + p2/100"], "p0 * s0 * s1"),
    R(_R + "sensitivity_analysis.multi_asset_portfolio.intermediate.v1",
      ["p2*p9/100 + p4*p11/100 + p6*p13/100", "p14 / 100"], "p0 * s1 * s0"),
    R(_R + "sensitivity_analysis.multi_factor_portfolio.advanced.v1",
      ["p4 * p1/100", "p5 * p2/100", "p6 * p3/100"], "p0 * (s0 + s1 + s2)"),
    R(_R + "sensitivity_analysis.portfolio_single_factor.basic.v1", ["p1 / 100"], "p0 * s0 * p2"),
    R(_R + "sensitivity_analysis.stock_sensitivity.basic.v1", ["p1 / 100"], "p0 * s0 * p2"),
    R(_R + "sensitivity_analysis.volatility_sensitivity.intermediate.v1", [], "p0 * p1"),
    R(_R + "stress_testing.multi_asset_portfolio.intermediate.v1",
      ["p2*p9/100 + p4*p11/100 + p6*p13/100", "p14 / 100"], "p0 * s1 * s0"),
    R(_R + "stress_testing.multi_factor_portfolio.advanced.v1",
      ["p0 * p1/100 * p3", "p0 * p2/100 * p4"], "s0 + s1"),
    R(_R + "stress_testing.portfolio_single_factor.basic.v1", ["p1 / 100"], "p0 * s0 * p2"),
    R(_R + "stress_testing.sensitivity_of_stock.basic.v1", ["p1 / 100"], "p0 * s0 * p2"),
    R(_R + "stress_testing.volatility_sensitivity.intermediate.v1", [], "p0 * p1"),
    R(_R + "var.multi_factor.advanced.v1",
      ["(p1 + p2 + p3) / 3", "1 + (100 - p5)/100"], "p0 * s0/100 * p4 * s1"),
    R(_R + "var.single_asset.basic.v1",
      ["p1 / 100", "1 + (100 - p3)/100"], "p0 * s0 * p2 * s1"),
    R(_R + "var.stock_return.basic.v1", ["p1 / 100", "p0 * s0"], "s1 * p2"),
    R(_R + "var.time_horizon.intermediate.v1", ["p1 / 100", "s0 * p2 * p3"], "p0 * s1"),
    # sustainable finance
    R(_S + "carbon_credits.comprehensive_strategy.advanced.v1",
      ["p3 * (1 - p6/100)", "p0 / s0", "max(0, s1 - p9)"], "s2 * s0 * (1 + p13/100) + p16 - p0"),
    R(_S + "carbon_credits.credit_purchase.basic.v1", [], "p0 / p3"),
    R(_S + "carbon_credits.offset_cost_savings.intermediate.v1",
      ["p0 * p4", "s0 * p7 / 100"], "s0 - s1"),
    R(_S + "esg_investing.dual_savings.intermediate.v1",
      ["p0 * 12", "p3 * 12", "s0 + s1 - p6"], "s2 + p9"),
    R(_S + "esg_investing.green_bond_yield.basic.v1", ["p0 * p3/100"], "s0 * p6"),
    R(_S + "esg_investing.multi_factor_synergy.advanced.v1",
      ["p3 * 12", "p9 * p12/100", "p15 * (s0 + s1 + p6)"], "s2 - p0"),
    R(_S + "esg_investing.project_roi.intermediate.v1",
      ["p3 * 12 - p6 + p9", "s0 * p12", "s1 / p0"], "s2 * 100"),
    R(_S + "esg_investing.simple_cost_savings.basic.v1", [], "p0 * p3"),
    R(_S + "green_bonds.compound_yield.basic.v1", ["(1 + p3/100)**p6", "p0 * s0"], "s1 - p0"),
    R(_S + "green_bonds.financing_cost_reduction.intermediate.v1",
      ["p0 * ((1 + p3/100)**p6 - 1)", "p3 - p9", "p0 * ((1 + s1/100)**p6 - 1)"], "s0 - s2"),
    R(_S + "green_bonds.synergy_benefit.intermediate.v1",
      ["p0 * ((1 + p3/100)**p6 - 1)", "p9 / p13 * p12", "s1 * p6"], "s0 + s2"),
    R(_S + "green_bonds.tax_incentive.basic.v1",
      ["p0 * ((1 + p3/100)**p6 - 1)", "s0 * p9/100"], "s0 + s1"),
    R(_S + "social_impact_investing.combined_cost_tax_savings.intermediate.v1",
      ["p0 * p3/100", "p6 * p9/100"], "s0 + s1"),
    R(_S + "social_impact_investing.energy_efficiency_savings.basic.v1", ["p3 / 100"], "p0 * (1 - s0)"),
    R(_S + "social_impact_investing.financing_cost_reduction.basic.v1", ["p3 / 100"], "p0 - s0"),
    R(_S + "social_impact_investing.multiphase_investment.advanced.v1",
      ["p1 * p4/100", "p8 * p11", "p15/100 * p18"], "s0 + s1 + s2"),
    R(_S + "social_impact_investing.supply_chain_integration.intermediate.v1",
      ["p0 * p3/100", "p6 + s0"], "p9 * s1"),
    R(_S + "sustainability_reporting.dual_operational_savings.intermediate.v1",
      ["p0 * p3/100", "p6 * p9/100"], "s0 + s1"),
    R(_S + "sustainability_reporting.energy_cost_savings.basic.v1", ["p3 / 100"], "p0 * s0"),
    R(_S + "sustainability_reporting.supply_chain_savings.intermediate.v1",
      ["p0 - p3", "s0 * p6/100"], "p3 + s1"),
    R(_S + "sustainability_reporting.sustainability_roi_analysis.advanced.v1",
      ["p3 + p6", "s0 * (1 + p9/100 + p12/100)", "s1 * p15 - p0"], "s2 / p0 * 100"),
    R(_S + "sustainability_reporting.waste_management_savings.basic.v1", ["p3 / 100"], "p0 * s0"),
]

REFERENCES: dict[str, Reference] = {}
for _ref in _ALL + _REST:
    if _ref.template_id in REFERENCES:
        raise ValueError(f"duplicate reference {_ref.template_id}")
    REFERENCES[_ref.template_id] = _ref

# Filled from the audit: the templates whose shipped (Sep 5) search program
# disagreed with its reference on at least one unlabelled draw.
FIXES: frozenset[str] = frozenset(
    {
        "fp.accounting_and_financial_reporting.cash_flow_statements.acquisition_cash_flow_impact.advanced.v1",
        "fp.corporate_finance.eps.eps_pref_div_split_weighted.advanced.v1",
        "fp.crypto_finance.defi.liquidity_pool_reward.intermediate.v1",
        "fp.crypto_finance.defi.multi_factor_portfolio.advanced.v1",
        "fp.crypto_finance.global_events_impact.global_macro_strategy.advanced.v1",
        "fp.crypto_finance.global_events_impact.market_sentiment_shift.intermediate.v1",
        "fp.crypto_finance.regulations.multi_factor_regulatory_risk.advanced.v1",
        "fp.crypto_finance.sentiments.multi_factor_sentiment.advanced.v1",
        "fp.crypto_finance.tokenomics.multi_factor_tokenomics.advanced.v1",
        "fp.crypto_finance.tokenomics.staking_reward_effect.intermediate.v1",
        "fp.crypto_finance.tokenomics.token_price_calculation.basic.v1",
        "fp.crypto_finance.transaction_analysis.bulk_transaction_fees.intermediate.v1",
        "fp.crypto_finance.transaction_analysis.cross_chain_transfer.intermediate.v1",
        "fp.crypto_finance.transaction_analysis.multi_factor_transaction.advanced.v1",
        "fp.crypto_finance.whale_detection.cross_exchange_impact.advanced.v1",
        "fp.crypto_finance.whale_detection.threshold_adjustment_detection.intermediate.v1",
        "fp.crypto_finance.whale_detection.wallet_activity_detection.basic.v1",
        "fp.finance_regulation.aml.multi_entity_ownership.intermediate.v1",
        "fp.finance_regulation.basel.multi_requirement.advanced.v1",
        "fp.finance_regulation.compliance.composite_risk.advanced.v1",
        "fp.finance_regulation.kyc.country_sector_risk.intermediate.v1",
        "fp.finance_regulation.kyc.source_of_funds.intermediate.v1",
        "fp.financial_markets.forex_trading.eur_to_gbp_cross_conversion.intermediate.v1",
        "fp.financial_markets.option_pricing.long_call_roi.intermediate.v1",
        "fp.financial_markets.stock_market_analysis.two_lot_sale_net_profit.advanced.v1",
        "fp.financial_ratios.effratio.asset_turnover_compare_periods.basic.v1",
        "fp.financial_ratios.liqratio.liquidity_minimum_quick_ratio.advanced.v1",
        "fp.financial_ratios.liqratio.quick_ratio_target.intermediate.v1",
        "fp.fintech.payment_technologies.batch_effective_fee.intermediate.v1",
        "fp.fintech.payment_technologies.cross_border_net.intermediate.v1",
        "fp.fintech.payment_technologies.effective_monthly_fee.advanced.v1",
        "fp.fintech.robo_advisors.tax_loss_savings.advanced.v1",
        "fp.investment_analysis.rar.three_asset_capm_portfolio.advanced.v1",
        "fp.mergers_and_acquisitions.synergies_and_cost_savings.synergy_basic_cost_reduction.basic.v1",
        "fp.personal_finance.personalinvest.diversification_risk.advanced.v1",
        "fp.personal_finance.taxcalc.foreign_tax_relief.advanced.v1",
    }
)

# Generator forms (stage 4) that must win even over a search result that
# passes the gate, because the audit found the search's choice degenerate.
GENFORM_FIXES: frozenset[str] = frozenset(
    {
        "fp.financial_markets.option_pricing.one_period_binomial_call.intermediate.v1",
        "fp.mergers_and_acquisitions.deal_structure.earnout_with_bonus_calculation.intermediate.v1",
    }
)

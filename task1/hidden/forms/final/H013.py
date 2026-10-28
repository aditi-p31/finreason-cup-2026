"""H013 (decimal, percent): managed rebalance vs buy-and-hold, wealth gap.

The reading, clause by clause (all wealth per 1 USD of original notional):
  * start: equity = w, bonds = 1 - w ("the complementary bond weight").
  * period 1: E = w * ge1, B = (1 - w) * gb1 (growth factors are multipliers).
  * midpoint: advisory charge c (a fraction of ORIGINAL notional, so c itself)
    comes entirely out of bonds: B -> B - c.
  * the advisor buys equity P and pays fee f * P, also from bonds.  The target
    fraction is the only equity weight stated, the starting weight w.  "Solve
    the purchase so equity equals its target fraction of wealth after both
    midpoint charges":  E + P = w * (E + B - c - f * P)
      =>  P = (w * (E + B - c) - E) / (1 + w * f).
    This is the literal linear solve.  The text asserts the portfolio is below
    target (so P > 0); if a draw's numbers put it above target, the same stated
    equation is kept (P < 0, fee term f * P signed) and info records it.
  * period 2: managed terminal = (E + P) * ge2 + (B - c - P - f * P) * gb2.
  * benchmark: fee-free buy-and-hold of the original positions through both
    periods, no rebalance, no charges: w * ge1 * ge2 + (1 - w) * gb1 * gb2.
  * final: (managed - benchmark) * 100, "as a percentage of original initial
    notional" (notional = 1).
Slots:
  * period_1_equity_value_checkpoint = w * ge1 (end of period 1, per unit notional).
  * period_1_bond_value_checkpoint = (1 - w) * gb1: the period-1 value after
    period-1 growth, before the midpoint charges (those happen "at the midpoint",
    after period 1).
"""
from hlib import num

KEY = "H013"


def solve(b):
    w = num(b, "starts with equity weight {N} and the complementary bond weight")
    ge1, gb1 = num(b, "During period 1, equity and bonds grow by factors {N} and {N}.")
    c = num(b, "fixed advisory charge equal to {N} of original initial notional")
    f = num(b, "pays transaction fee rate {N} on the purchase")
    ge2, gb2 = num(b, "During period 2, equity and bonds grow by factors {N} and {N}.")

    e1 = w * ge1
    b1 = (1 - w) * gb1
    b_after_charge = b1 - c
    purchase = (w * (e1 + b_after_charge) - e1) / (1 + w * f)
    fee = f * purchase
    e_mid = e1 + purchase
    b_mid = b_after_charge - purchase - fee
    managed = e_mid * ge2 + b_mid * gb2
    bench = w * ge1 * ge2 + (1 - w) * gb1 * gb2
    final = (managed - bench) * 100
    return {
        "final": final,
        "slots": {
            "period_1_equity_value_checkpoint": e1,
            "period_1_bond_value_checkpoint": b1,
        },
        "info": {
            "purchase": purchase,
            "purchase_positive": purchase > 0,
            "equity_weight_after_charge_before_trade": e1 / (e1 + b_after_charge),
            "post_trade_equity_share": e_mid / (e_mid + b_mid),
            "bond_after_trade": b_mid,
            "managed_terminal": managed,
            "benchmark_terminal": bench,
        },
    }

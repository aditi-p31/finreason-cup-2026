"""H023 (enum): two capital plans against a three-stage covenant-ratchet ceiling.

The reading:
* Ceiling starts at the stated value (1.00).  Each of three stages multiplies
  the remaining ceiling by (1 - t), so the final ceiling = start x (1 - t)^3
  (the text states "(1-t)^3" with start 1.00).
* Plan A: debt = current debt + borrowing, equity = current equity + added equity.
* Plan B: debt = current debt - repayment, equity = current equity + added equity.
* Ratio = debt / equity (debt-to-equity).
* "qualifies only when its exact post-transaction ratio does not exceed the
  final ceiling": ratio <= ceiling (inclusive).
* Both qualify: lower ratio wins, plan_a on an exact tie.  One qualifies: it.
  Neither: neither_plan.
Slot one_stage_leverage_cap_checkpoint = start x (1 - t), the ceiling remaining
after one stage.
"""
from hlib import num, pick_two

KEY = "H023"


def solve(b):
    debt, eq = num(b, "company with current debt {N} and current equity {N}.")
    start = num(b, "ceiling starts at {N}.")
    t = num(b, "by the same fraction t={N},")
    add_d, add_ea = num(b, "Plan A adds borrowing {N} and equity {N}.")
    rep_d, add_eb = num(b, "Plan B repays debt {N} and adds equity {N}.")
    one = start * (1 - t)
    ceiling = start * (1 - t) ** 3
    ra = (debt + add_d) / (eq + add_ea)
    rb = (debt - rep_d) / (eq + add_eb)
    ok_a = ra <= ceiling
    ok_b = rb <= ceiling
    label = pick_two(ok_a, ok_b, ra, rb, a="plan_a", b="plan_b",
                     neither="neither_plan", better="lower", tie="plan_a")
    return {"final": label,
            "slots": {"one_stage_leverage_cap_checkpoint": one},
            "info": {"ceiling": ceiling, "ratio_a": ra, "ratio_b": rb,
                     "margin_a": ceiling - ra, "margin_b": ceiling - rb}}

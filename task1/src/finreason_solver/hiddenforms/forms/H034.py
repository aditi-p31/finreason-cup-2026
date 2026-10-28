"""H034 (decimal, usd): maximum exposure within a remediation budget.

The reading: total spending = capital + liquidity + ratio * max(exposure - T, 0).
"Can spend at most L" / "within budget" => spending <= L (inclusive).
The budget left for the exposure charge is L - capital - liquidity; the largest
exposure keeping ratio * (X - T) <= that budget is X = T + (L - capital - liquidity) / ratio.
(When the charge budget is exactly zero, X = T: every exposure up to T is free
and any excess costs more than zero, so T is the maximum.)
Slot charge_budget_checkpoint = L - capital - liquidity, the "budget available
for the exposure charge".
"""
from hlib import num

KEY = "H034"


def solve(b):
    budget = num(b, "can spend at most {N} on all remediation")
    cap_cost = num(b, "Capital remediation already requires {N},")
    liq_cost = num(b, "liquidity remediation requires {N},")
    thr, ratio = num(b, "any exposure above {N} incurs a charge at ratio {N} of the excess")
    charge_budget = budget - cap_cost - liq_cost
    x_max = thr + charge_budget / ratio
    return {
        "final": x_max,
        "slots": {"charge_budget_checkpoint": charge_budget},
        "info": {"charge_budget": charge_budget, "threshold": thr, "ratio": ratio,
                 "budget_exceeds_fixed_costs": charge_budget > 0},
    }

"""H071 (usd): maximum portfolio value exhausting a combined loss budget.

The reading: market-shock loss = V * shock ratio * loss sensitivity; liquidity
cost = V * spread ratio; both scale with the same V.  "exactly exhausts the
combined loss budget": V * (shock * sensitivity + spread) = budget, so
V = budget / (shock * sensitivity + spread).
Slot market_ratio_checkpoint ("market-shock loss ratio", ratio) =
shock ratio * loss sensitivity (market-shock loss per unit of portfolio value).
"""
from hlib import num

KEY = "H071"


def solve(b):
    budget = num(b, "liquidity-spread cost within {N}.")
    shock, sens, spread = num(b, "The market shock ratio is {N}, its loss sensitivity is {N}, "
                                 "and the liquidity spread ratio is {N}.")
    mratio = shock * sens
    v = budget / (mratio + spread)
    return {"final": v,
            "slots": {"market_ratio_checkpoint": mratio},
            "info": {"combined_ratio": mratio + spread}}

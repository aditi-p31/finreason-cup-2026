"""H050 (decimal, usd): Plan A savings versus Plan B over a horizon.

The reading, clause by clause:
* horizon volume = monthly volume * months; horizon count = transfers per
  month * months.
* Plan X total = rate * horizon volume + per-transfer fee * horizon count
  + monthly subscription * months + setup fee (setup charged exactly once).
* Plan B's "charges r, f, s" list is in the same order as Plan A's
  (proportional rate, fee per transfer, monthly subscription).
* savings = Plan B total - Plan A total, signed (no floor).
Slots: horizon_volume_checkpoint = monthly volume * months;
horizon_count_checkpoint = transfers per month * months.
"""
from hlib import num

KEY = "H050"


def solve(b):
    vol, n, months = num(b, "A customer expects monthly transfer volume {N} and {N} transfers per month for {N} months")
    ra, fa, sa, ua = num(b, "Plan A charges proportional transfer rate {N}, fee {N} per transfer, monthly subscription {N}, and one-time setup fee {N}.")
    rb, fb, sb, ub = num(b, "Plan B charges {N}, {N}, {N}, and one-time setup fee {N}.")

    hv = vol * months
    hc = n * months
    cost_a = ra * hv + fa * hc + sa * months + ua
    cost_b = rb * hv + fb * hc + sb * months + ub
    return {"final": cost_b - cost_a,
            "slots": {"horizon_volume_checkpoint": hv, "horizon_count_checkpoint": hc},
            "info": {"cost_a": cost_a, "cost_b": cost_b}}

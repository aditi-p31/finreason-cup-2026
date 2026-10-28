"""H065 (decimal, percent): TWR minus Modified Dietz, signed percentage points.

The reading:
* V0 = beginning value, Vb = value immediately before the contribution C,
  which arrives after fraction t of the period.  V1 = ending value, which
  excludes the terminal distribution D paid at period end.
* TWR subperiod 1 = Vb / V0 - 1.  Subperiod 2 starts at Vb + C and ends at
  V1 + D (the distribution is paid at that same end instant, so the
  pre-distribution end value is V1 + D).  TWR = (Vb/V0)((V1 + D)/(Vb + C)) - 1.
* Modified Dietz: gain = V1 - V0 - (C - D); denominator = V0 + C x (1 - t)
  + (-D) x 0 (the distribution at period end has zero remaining weight;
  the contribution's remaining-period weight is 1 - t).
* Answer = (TWR - MD) x 100 in signed percentage points.
Slot period_one_return_checkpoint = Vb / V0 - 1 (ratio).
"""
from hlib import num

KEY = "H065"


def solve(b):
    v0 = num(b, "begins a measurement period at value {N}.")
    c, t, vb = num(b, "Immediately before a contribution of {N} is added after {N} of the period has elapsed, the account value is {N}.")
    v1, d = num(b, "the post-distribution account value is {N} and a terminal cash distribution of {N} is paid")
    r1 = vb / v0 - 1
    r2 = (v1 + d) / (vb + c) - 1
    twr = (1 + r1) * (1 + r2) - 1
    weight_c = 1 - t
    md = (v1 - v0 - (c - d)) / (v0 + c * weight_c - d * 0)
    return {"final": (twr - md) * 100,
            "slots": {"period_one_return_checkpoint": r1},
            "info": {"twr": twr, "md": md, "r2": r2}}

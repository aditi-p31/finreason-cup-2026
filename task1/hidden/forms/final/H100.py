"""H100 (decimal, percent): Modified Dietz ROI with a terminal distribution.

The reading:
* Begin value BMV; contribution C at elapsed fraction t, weighted by the
  fraction of the period remaining w = 1 - t.
* Ending value EMV excludes a terminal distribution D paid at period end
  (an outflow, weight 0 in the denominator).
* Net external flow = C - D.  Gain = EMV - BMV - (C - D).
* Capital base = BMV + w * C + 0 * (-D).
* ROI = gain / base, reported as a percentage (x 100).
Slot weighted_contribution_checkpoint = w * C (USD).
"""
from hlib import num

KEY = "H100"


def solve(b):
    bmv = num(b, "begins a measurement period at value {N}.")
    c, t = num(b, "A contribution of {N} is added after {N} of the period has elapsed.")
    emv, dist = num(b, "the post-distribution account value is {N} and a terminal cash distribution of {N} is paid")
    w = 1 - t
    wc = w * c
    gain = emv - bmv - (c - dist)
    base = bmv + wc
    return {
        "final": gain / base * 100,
        "slots": {"weighted_contribution_checkpoint": wc},
        "info": {"gain": gain, "base": base},
    }

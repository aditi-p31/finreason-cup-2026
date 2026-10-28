"""H103 (enum Enhanced review / Standard review): aggregate + decayed spike rule.

The reading:
  * aggregate volume = t1 + t2 + t3 ("three related cash transactions").
  * effective spike threshold = baseline * (1 - f) ** 3 ("reduce ... by fraction f of
    its then-current value" at each of three stages, no replenishment).
  * spike ratio = max(t1, t2, t3) / historical average.
  * two critical flags: "The policy also records <B1> and <B2>."
  * Enhanced review when (aggregate > threshold AND spike > effective threshold)
    ("strictly exceeds" -> > on both), OR flag1 OR flag2; otherwise Standard review.
Slot spike_threshold_residual_factor_checkpoint = 1 - f, the threshold fraction
retained after one stage (ratio).
"""
from hlib import num, flag, ipow, first_true

KEY = "H103"


def solve(b):
    t1, t2, t3 = num(b, "Three related cash transactions are {N}, {N}, and {N}.")
    agg_thr = num(b, "The aggregate review threshold is {N}.")
    hist, base = num(b, "historical average cash transaction is {N}, and the baseline "
                        "largest-to-history spike-ratio threshold is {N}.")
    f = num(b, "reduce the surviving spike threshold by fraction {N} of its "
               "then-current value")
    flag1 = flag(b, "The policy also records {B} and")
    flag2 = flag(b, "and {B}. Return Enhanced review")

    agg = t1 + t2 + t3
    retain = 1 - f
    eff = base * ipow(retain, 3)
    spike = max(t1, t2, t3) / hist
    agg_hit = agg > agg_thr
    spike_hit = spike > eff
    label = first_true([((agg_hit and spike_hit) or flag1 or flag2, "Enhanced review")],
                       otherwise="Standard review")
    return {
        "final": label,
        "slots": {"spike_threshold_residual_factor_checkpoint": retain},
        "info": {"aggregate": agg, "aggregate_threshold": agg_thr, "agg_hit": agg_hit,
                 "spike_ratio": spike, "effective_threshold": eff,
                 "spike_hit": spike_hit, "flag1": flag1, "flag2": flag2},
    }

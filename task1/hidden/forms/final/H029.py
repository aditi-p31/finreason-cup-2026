"""H029 (decimal, usd): next transfer that makes a rolling total exceed an adjusted whale threshold by an exact margin.

Reading:
* adjusted threshold = base threshold * (1 + r) ("increased by risk-adjustment
  ratio r").
* rolling total = prior1 + prior2 + x.
* "exceed the adjusted threshold by exactly E": rolling total - adjusted = E,
  so x = base * (1 + r) + E - prior1 - prior2.
* The recipe is an exact equation, so x is reported as solved, with no floor at
  zero (a clamp would break "exactly").  When the two prior transfers already
  exceed the adjusted threshold by more than E, x comes out negative.
* Slot threshold_adjustment_factor_checkpoint: the multiplicative factor = 1 + r.
"""
from hlib import num

KEY = "H029"


def solve(b):
    p1, p2 = num(b, "two prior transfers of {N} USD and {N} USD in the current")
    base = num(b, "base rolling whale threshold is {N} USD")
    r = num(b, "increased by risk-adjustment ratio {N}.")
    excess = num(b, "exceed the adjusted threshold by exactly {N} USD")
    factor = 1 + r
    adjusted = base * factor
    x = adjusted + excess - p1 - p2
    return {"final": x,
            "slots": {"threshold_adjustment_factor_checkpoint": factor},
            "info": {"adjusted_threshold": adjusted, "prior_total": p1 + p2,
                     "prior_excess_over_adjusted": p1 + p2 - adjusted}}

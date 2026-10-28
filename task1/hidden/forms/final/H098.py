"""H098 (decimal, percent): maximum risky-asset weight under a stress floor and cap.

The reading, clause by clause:
* portfolio value V; stressed value must remain at or above floor L (L < V).
* the risky asset (weight w, allocated amount w*V) loses fraction d of its
  allocated amount; everything else keeps its value, so stressed value =
  V - d * w * V.  "at or above" -> V - d*w*V >= L -> w <= (V - L) / (d * V).
* policy caps the weight at c, so the exact maximum permitted weight is
  min((V - L) / (d * V), c), applied to the unrounded exact weight.
* reported as a percentage (x 100), rounded only at the end.

Slot loss_budget_checkpoint "allowable dollar loss under the floor" = V - L.
"""
from hlib import num

KEY = "H098"


def solve(b):
    value, floor = num(b, "An investor has a portfolio worth {N} and requires its stressed value "
                          "to remain at or above {N},")
    d = num(b, "the risky asset loses {N} of its allocated amount")
    cap = num(b, "caps the risky asset's portfolio weight at {N}.")
    budget = value - floor
    stress_w = budget / (d * value)
    w = min(stress_w, cap)
    return {
        "final": w * 100,
        "slots": {"loss_budget_checkpoint": budget},
        "info": {"stress_weight": stress_w, "cap": cap},
    }

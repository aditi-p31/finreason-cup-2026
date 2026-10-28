"""H056 (decimal, usd): capital charge = max(modeled factor loss, external stress loss).

The reading, clause by clause:
* two factor shock ratios s1, s2 with respective loss sensitivities k1, k2;
  each linear factor rate = shock * its sensitivity.
* "Their joint effect is the product of both shocks and j": joint rate =
  s1 * s2 * j.
* "A concentration ratio c adds its squared value to the modeled loss rate":
  + c^2.
* modeled loss rate = s1*k1 + s2*k2 + s1*s2*j + c^2; modeled loss = portfolio
  value * modeled loss rate.
* required capital charge = max(modeled loss, external stress loss).
  Amounts are used in the units given (answer unit usd, no rescaling).

Slot joint_ratio_checkpoint "joint interaction loss ratio" = s1 * s2 * j.
"""
from hlib import num

KEY = "H056"


def solve(b):
    value, s1, s2 = num(b, "A portfolio worth {N} has factor shock ratios {N} and {N},")
    k1, k2 = num(b, "with respective loss sensitivities {N} and {N}.")
    j = num(b, "Their joint effect is the product of both shocks and {N}.")
    c = num(b, "A concentration ratio {N} adds its squared value")
    ext = num(b, "external stress loss {N}")
    joint = s1 * s2 * j
    rate = s1 * k1 + s2 * k2 + joint + c * c
    modeled = value * rate
    final = max(modeled, ext)
    return {
        "final": final,
        "slots": {"joint_ratio_checkpoint": joint},
        "info": {"modeled_rate": rate, "modeled_loss": modeled, "external": ext},
    }

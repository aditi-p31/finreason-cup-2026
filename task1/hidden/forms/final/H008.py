"""H008 (decimal, usd_million): residual value implied by a target carrying amount.

The reading: straight-line depreciation charges the elapsed fraction f of the
depreciable base (cost - residual).  Carrying amount = cost - f*(cost - residual).
Setting that equal to the target carrying amount CA:
    accumulated depreciation = cost - CA
    cost - residual = (cost - CA) / f
    residual = cost - (cost - CA) / f
All amounts are already in USD millions; no rescaling.
Slot implied_depreciation_checkpoint ("recover accumulated depreciation from cost
and target carrying amount") = cost - CA.
"""
from hlib import num

KEY = "H008"


def solve(b):
    cost = num(b, "An asset has original cost {N} in USD millions")
    frac = num(b, "Under straight-line depreciation, {N} of its depreciable life has elapsed")
    target = num(b, "target carrying amount of {N} at that point")
    acc_dep = cost - target
    base = acc_dep / frac
    residual = cost - base
    return {"final": residual,
            "slots": {"implied_depreciation_checkpoint": acc_dep},
            "info": {"cost": cost, "elapsed_fraction": frac, "target": target,
                     "depreciable_base": base}}

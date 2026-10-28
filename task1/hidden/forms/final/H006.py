"""H006 (decimal, percent): signed factor shock for a target portfolio value change.

The reading:
* Exposed value = portfolio value x exposed share ("only share s is exposed").
* The exposed portion has signed sensitivity beta, so a factor shock x changes
  portfolio value by exposed value x beta x x.  The unexposed part does not move.
* Required shock x = target change / (exposed value x beta), kept signed.
* "report that shock as a percentage": return x x 100.
Slot exposed_value_checkpoint = portfolio value x exposed share (USD), the
"factor-exposed portfolio value".
"""
from hlib import num

KEY = "H006"


def solve(b):
    value, share = num(b, "A portfolio is worth {N}, but only share {N} is exposed to one factor.")
    beta = num(b, "The exposed portion has signed sensitivity {N}.")
    target = num(b, "target portfolio value change {N},")
    exposed = value * share
    shock = target / (exposed * beta)
    return {"final": shock * 100,
            "slots": {"exposed_value_checkpoint": exposed},
            "info": {"shock_ratio": shock}}

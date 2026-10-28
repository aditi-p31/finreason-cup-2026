"""H105 (decimal, count): beneficiary scale meeting a social-value surplus.

The reading, clause by clause:
* combined fixed costs = launch cost + monitoring cost.
* required social value = combined fixed costs x (1 + surplus ratio) (stated
  "equivalently").
* scale that "exactly meets" the requirement = required value / value per unit.
  No integer rounding: the spec rounds the count half up to 2 decimals.
Slot monitoring_surplus_value_checkpoint = the surplus requirement attributable to
monitoring cost = monitoring cost x surplus ratio (the part of the required
surplus over costs that comes from the monitoring cost).  The alternative reading
monitoring cost x (1 + ratio) (monitoring's share of the whole required value) is
recorded in info.
"""
from hlib import num

KEY = "H105"


def solve(b):
    launch, monitor = num(b, "has launch cost {N} and monitoring cost {N}.")
    v = num(b, "create net monetized social value {N}.")
    s = num(b, "combined fixed costs by the surplus ratio {N};")
    fixed = launch + monitor
    required = fixed * (1 + s)
    scale = required / v
    return {"final": scale,
            "slots": {"monitoring_surplus_value_checkpoint": monitor * s},
            "info": {"required_value": required,
                     "monitor_required_value_alt": monitor * (1 + s)}}

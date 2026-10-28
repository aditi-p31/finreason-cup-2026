"""H005 (decimal, usd_per_ton_co2e): carbon-credit break-even price.

The reading:
* One credit covers one ton, so credits bought = tons covered.
* Planned internal abatement = capacity x committed utilization (tons CO2e).
* Internal abatement cost = mobilization fixed cost + per-ton variable cost x
  planned tons ("plus N USD for each ton internally abated").
* Break-even credit price p solves p x planned = internal cost, so
  p = internal cost / planned (USD per ton).
Slot planned_abatement_checkpoint = capacity x utilization, the "internally
planned reduction quantity" in tons.
"""
from hlib import num

KEY = "H005"


def solve(b):
    cap = num(b, "internal abatement capacity {N} tons of CO2e")
    util = num(b, "commits to utilization {N}.")
    fixed, var = num(b, "Mobilizing internal abatement costs {N} USD, plus {N} USD for each ton internally abated")
    planned = cap * util
    cost = fixed + var * planned
    price = cost / planned
    return {"final": price,
            "slots": {"planned_abatement_checkpoint": planned},
            "info": {"internal_cost": cost}}

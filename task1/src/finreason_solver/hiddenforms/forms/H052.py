"""H052 (decimal, percent): required waste-cost reduction rate.

The reading: energy savings = energy expenditure * energy-reduction ratio.
Combined savings = energy savings + waste expenditure * waste rate = target, so
waste rate = (target - energy savings) / waste expenditure, "expressed as a
percentage" -> times 100.
Slot energy_savings_checkpoint = energy expenditure * energy-reduction ratio (usd).
"""
from hlib import num

KEY = "H052"


def solve(b):
    energy, ratio = num(b, "annual energy expenditure {N} and an achieved "
                           "energy-reduction ratio {N}.")
    waste = num(b, "Annual waste-management expenditure is {N}.")
    target = num(b, "combined annual savings target {N},")
    energy_savings = energy * ratio
    rate = (target - energy_savings) / waste
    return {
        "final": rate * 100,
        "slots": {"energy_savings_checkpoint": energy_savings},
        "info": {"waste_savings_needed": target - energy_savings, "rate_ratio": rate},
    }

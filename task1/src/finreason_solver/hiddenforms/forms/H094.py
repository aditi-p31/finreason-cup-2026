"""H094 (decimal, percent): one Newton-Raphson IRR step from a trial rate.

The reading: NPV(r) = -C0 + C1 / (1 + r) + C2 / (1 + r) ** 2 at trial r0.
dNPV/dr = -C1 / (1 + r) ** 2 - 2 * C2 / (1 + r) ** 3 (negative); "using the positive
magnitude of the NPV derivative" and "the update moves upward" give
r1 = r0 + NPV(r0) / |dNPV/dr(r0)|, identical to the standard r0 - NPV / NPV'.
One update only; report r1 as an annual percentage (* 100).
Slot year_two_present_value_checkpoint = C2 / (1 + r0) ** 2 (usd).
"""
from hlib import num, ipow

KEY = "H094"


def solve(b):
    c0 = num(b, "requires an initial outlay of {N} at time 0")
    c1 = num(b, "pays {N} at the end of year 1")
    c2 = num(b, "pays {N} at the end of year 2")
    r0 = num(b, "annual effective trial rate {N},")
    d = 1 + r0
    pv1 = c1 / d
    pv2 = c2 / ipow(d, 2)
    npv = -c0 + pv1 + pv2
    deriv = -c1 / ipow(d, 2) - 2 * c2 / ipow(d, 3)
    r1 = r0 + npv / abs(deriv)
    return {
        "final": r1 * 100,
        "slots": {"year_two_present_value_checkpoint": pv2},
        "info": {"npv_trial": npv, "npv_positive": npv > 0, "derivative": deriv,
                 "step": npv / abs(deriv)},
    }

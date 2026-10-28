"""H115 (decimal, percent): capped Newton step on an after-tax sale NPV.

The reading:
  * year-2 net sale proceeds N = gross price * (1 - selling-cost fraction)
    ("selling costs equal the fraction k of gross price").
  * gain = N - basis (basis unchanged by the year-1 distribution); tax =
    tax rate * max(gain, 0) ("of the positive gain").
  * year-2 cash flow CF2 = N - tax; year-1 cash flow = the after-tax distribution D1.
  * NPV(r) = -C0 + D1 / (1 + r) + CF2 / (1 + r) ** 2 at trial r0.
  * derivative magnitude |NPV'(r0)| = D1 / (1 + r0) ** 2 + 2 * CF2 / (1 + r0) ** 3;
    raw correction = NPV(r0) / |NPV'(r0)| ("positive Newton-Raphson correction
    using the negative-derivative magnitude").
  * r1 = r0 + min(raw correction, cap) ("add the smaller of the raw correction and
    cap to the trial rate"); report r1 * 100 as an annual percentage.
Slot net_sale_proceeds_after_cost_checkpoint = N (after selling costs, before
gain tax), usd.
"""
from hlib import num, ipow, pos

KEY = "H115"


def solve(b):
    c0, basis = num(b, "An investment requires {N} at time 0 and has unchanged tax basis {N}.")
    d1 = num(b, "It pays the after-tax distribution {N} at the end of year 1")
    gross, k = num(b, "At the end of year 2 it is sold for {N}; selling costs equal "
                      "the fraction {N} of gross price")
    tax_rate = num(b, "capital-gains tax equals {N} of the positive gain")
    r0 = num(b, "Starting from annual effective trial rate {N},")
    cap = num(b, "Apply the fixed absolute rate-step cap {N},")

    net_sale = gross * (1 - k)
    gain = net_sale - basis
    tax = tax_rate * pos(gain)
    cf2 = net_sale - tax
    d = 1 + r0
    npv = -c0 + d1 / d + cf2 / ipow(d, 2)
    deriv_mag = d1 / ipow(d, 2) + 2 * cf2 / ipow(d, 3)
    raw = npv / deriv_mag
    step = min(raw, cap)
    r1 = r0 + step
    return {
        "final": r1 * 100,
        "slots": {"net_sale_proceeds_after_cost_checkpoint": net_sale},
        "info": {"gain": gain, "tax": tax, "cf2": cf2, "npv_trial": npv,
                 "raw_correction": raw, "cap": cap, "cap_binding": raw > cap,
                 "raw_positive": raw > 0},
    }

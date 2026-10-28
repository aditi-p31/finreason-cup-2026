"""H074 (decimal, usd): maximum total principal under a repayment cap.

The reading: principal P split into green share s and conventional share 1 - s
("the remaining principal").  Green compound maturity factor
Fg = (1 + yg) ** ng; conventional factor Fc = (1 + yc) ** nc (annual compounding).
Repayment = P * s * Fg + P * (1 - s) * Fc; setting it exactly equal to the cap
gives P = cap / (s * Fg + (1 - s) * Fc).
Slot green_maturity_factor_checkpoint = Fg, the full-term compound factor of the
green tranche (multiple).
"""
from hlib import num, ipow

KEY = "H074"


def solve(b):
    s, yg, ng = num(b, "The green tranche receives share {N}, earns annual yield "
                       "ratio {N}, and compounds for {N} annual periods.")
    yc, nc = num(b, "conventional tranche, which earns annual yield ratio {N} and "
                    "compounds for {N} annual periods.")
    cap = num(b, "total maturity-repayment cap {N},")
    fg = ipow(1 + yg, ng)
    fc = ipow(1 + yc, nc)
    principal = cap / (s * fg + (1 - s) * fc)
    return {
        "final": principal,
        "slots": {"green_maturity_factor_checkpoint": fg},
        "info": {"conventional_factor": fc, "blended_factor": s * fg + (1 - s) * fc},
    }

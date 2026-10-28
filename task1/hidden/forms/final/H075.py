"""H075 (decimal, usd): initial principal given a later contribution.

The reading:
* The initial principal P compounds for the stated n whole annual periods:
  P * (1 + r)^n.
* The later contribution C "earns the same rate" for the stated m whole
  periods that remain from its deposit boundary: C * (1 + r)^m.
* The account "must reach" target T: P * (1 + r)^n + C * (1 + r)^m = T,
  so P = (T - C * (1 + r)^m) / (1 + r)^n.
Slot: compound growth factor applied to the later contribution = (1 + r)^m.

The text states m > n on every draw (the contribution has more periods left
than the account horizon); the recipe is applied literally with the stated
exponents.  When C * (1 + r)^m exceeds T the required principal is negative;
the text gives no floor at zero, so no floor is applied.
"""
from hlib import num, ipow

KEY = "H075"


def solve(b):
    target, n, r = num(b, "An account must reach {N} USD after {N} whole annual compounding periods at annual rate ratio {N}.")
    c = num(b, "A later contribution of {N} USD is deposited")
    m = num(b, "from which exactly {N} whole periods remain")

    g_late = ipow(1 + r, m)
    p = (target - c * g_late) / ipow(1 + r, n)
    return {
        "final": p,
        "slots": {"later_contribution_growth_checkpoint": g_late},
        "info": {"n": n, "m": m, "contribution_fv": c * g_late},
    }

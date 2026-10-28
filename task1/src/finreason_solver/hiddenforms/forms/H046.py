"""H046 (decimal, usd): level-growing withdrawal W from a three-year bridge.

Reading:
* opening capital P, balance earns r each year; year-end withdrawals
  W, W*(1+g), W*(1+g)^2 after years 1, 2, 3 (g is the "one plus g" growth).
* B1 = P(1+r) - W; B2 = B1(1+r) - W(1+g); B3 = B2(1+r) - W(1+g)^2 = reserve.
  => P(1+r)^3 - W[(1+r)^2 + (1+r)(1+g) + (1+g)^2] = reserve
  => W = (P(1+r)^3 - reserve) / [(1+r)^2 + (1+r)(1+g) + (1+g)^2].
* Slot two_year_gross_capital_checkpoint: gross two-year value of the opening
  capital before withdrawals = P(1+r)^2.
"""
from hlib import num, ipow

KEY = "H046"


def solve(b):
    p = num(b, "three-year retirement bridge with {N}.")
    r = num(b, "The remaining balance earns {N} annually.")
    g = num(b, "W times one plus {N} after year 2")
    reserve = num(b, "Immediately after the third withdrawal, {N} must remain.")
    a = 1 + r
    q = 1 + g
    w = (p * ipow(a, 3) - reserve) / (ipow(a, 2) + a * q + ipow(q, 2))
    # re-check the reserve equality by rolling the balance forward exactly
    b1 = p * a - w
    b2 = b1 * a - w * q
    b3 = b2 * a - w * ipow(q, 2)
    assert b3 == reserve
    return {"final": w,
            "slots": {"two_year_gross_capital_checkpoint": p * ipow(a, 2)},
            "info": {"b1": b1, "b2": b2, "b3": b3}}

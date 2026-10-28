"""H014 (decimal, percent): required total return for a target mean-variance score.

The reading, clause by clause:
* w_A is stated; "Asset B receives the complementary weight" -> w_B = 1 - w_A.
* Volatilities vol_A, vol_B are stated in that order.
* "Use the stress contribution when X is at least Y" -> stress if X >= Y
  (inclusive, "at least"), otherwise the base contribution.  The contribution
  is used as supplied ("each already equals twice the product of both weights
  and the regime covariance"), so it is added as is.
* variance = (w_A*vol_A)^2 + (w_B*vol_B)^2 + selected contribution.
* score = (R - rf) - lambda * variance.  Setting score = target gives
  R = target + rf + lambda * variance.
* "Report a percentage" -> final = 100 * R.
Slots: weighted volatility of asset A = w_A * vol_A and of asset B =
w_B * vol_B (ratio units, the weight-scaled volatilities that get squared).
"""
from hlib import num

KEY = "H014"


def solve(b):
    wa = num(b, "Asset A has portfolio weight {N} and Asset B receives the complementary weight")
    wb = 1 - wa
    va, vb = num(b, "Their return volatilities are {N} and {N}.")
    base, stress = num(b, "base weighted covariance cross-term contribution {N} and stress contribution {N};")
    x, y = num(b, "Use the stress contribution when {N} is at least {N}, and otherwise use the base contribution")
    lam = num(b, "The score equals portfolio excess return minus {N} times variance")
    target, rf = num(b, "makes this score equal {N} when the risk-free rate is {N}?")

    contrib = stress if x >= y else base
    wva = wa * va
    wvb = wb * vb
    var = wva * wva + wvb * wvb + contrib
    total_return = target + rf + lam * var
    return {
        "final": total_return * 100,
        "slots": {
            "weighted_volatility_a_checkpoint": wva,
            "weighted_volatility_b_checkpoint": wvb,
        },
        "info": {"stress_used": x >= y, "stress_margin": x - y, "variance": var},
    }

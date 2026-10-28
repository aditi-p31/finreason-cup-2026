"""H113 (usd): required capital as the larger of a common-factor VaR and stress loss.

The reading: the two signed loadings load on the same common factor, and the
question says to "aggregate the loadings before constructing the variance
radicand": radicand = (l1 + l2)^2, portfolio sigma = sqrt(radicand) = |l1 + l2|
(a ratio, as the loadings are ratios).  Loss measure = portfolio value *
confidence multiplier * sigma + liquidity charge (the liquidity charge is added
as a stated amount; unlike the loadings it is not said to be a ratio).
Required capital = max(loss measure, stress loss) ("the larger loss measure").
Slot portfolio_sigma_checkpoint = sigma (ratio).
"""
from hlib import num, sqrt

KEY = "H113"


def solve(b):
    value, l1, l2 = num(b, "A portfolio worth {N} has signed weighted common-factor return loadings {N} and {N},")
    mult = num(b, "Apply confidence multiplier {N},")
    liq = num(b, "add liquidity charge {N},")
    stress = num(b, "compare the result with stress loss {N}.")
    agg = l1 + l2
    sigma = sqrt(agg * agg)
    var_loss = value * mult * sigma + liq
    return {"final": max(var_loss, stress),
            "slots": {"portfolio_sigma_checkpoint": sigma},
            "info": {"var_plus_liquidity": var_loss, "stress_loss": stress}}

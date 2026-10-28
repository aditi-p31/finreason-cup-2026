"""H032 (percent): maximum management fee under Sharpe and Jensen-alpha floors.

The reading: net return = gross - fee (fee reduces return one-for-one; sigma,
beta, market return and rf unchanged).
  Sharpe constraint  (gross - fee - rf) / sigma >= S_min   ("at least" -> >=)
      -> fee <= gross - rf - S_min * sigma
  Jensen alpha       (gross - fee) - [rf + beta * (Rm - rf)] >= alpha_min  (>=)
      -> fee <= gross - rf - beta * (Rm - rf) - alpha_min
Both inequalities are inclusive, so the exact maximum fee satisfying both is the
minimum of the two bounds, reported as a percentage (* 100).  The question
states no floor at zero, so a negative bound is returned as computed: "the
exact maximum annual management-fee rate that satisfies both constraints".
Slot market_premium_checkpoint ("market risk premium used by the alpha
constraint", ratio) = Rm - rf.
"""
from hlib import num

KEY = "H032"


def solve(b):
    gross, sigma, beta = num(b, "gross expected return {N}, volatility {N}, and beta {N}.")
    rm, rf = num(b, "The market return is {N} and the risk-free rate is {N}.")
    s_min, a_min = num(b, "retain a Sharpe ratio of at least {N} and Jensen's alpha of at least {N}.")
    mrp = rm - rf
    fee_sharpe = gross - rf - s_min * sigma
    fee_alpha = gross - rf - beta * mrp - a_min
    fee = min(fee_sharpe, fee_alpha)
    # exact re-test of both constraints at the unrounded rate
    net = gross - fee
    assert (net - rf) / sigma >= s_min
    assert net - (rf + beta * mrp) >= a_min
    return {"final": fee * 100,
            "slots": {"market_premium_checkpoint": mrp},
            "info": {"fee_bound_sharpe": fee_sharpe, "fee_bound_alpha": fee_alpha}}

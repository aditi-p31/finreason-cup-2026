"""H067 (decimal, usd): premium threshold at which call ROI equals a target.

The reading:
  intrinsic payoff I = terminal price - strike (per share).
  ROI = (I - fee - premium) / premium; set ROI = target ratio k (k given as a
  decimal ratio, "0.20 means 20%").
  I - fee - P = k * P  =>  P = (I - fee) / (1 + k).
  Report the exact threshold (run_forms rounds half up to cents).
Slot intrinsic_checkpoint = I = terminal price - strike.
"""
from hlib import num

KEY = "H067"


def solve(b):
    s, k_strike = num(b, "at terminal stock price {N} with strike price {N}.")
    fee = num(b, "Deduct the additional settlement fee {N}, which is separate")
    target = num(b, "For target ratio {N}, where 0.20 means 20%")
    intrinsic = s - k_strike
    prem = (intrinsic - fee) / (1 + target)
    return {"final": prem,
            "slots": {"intrinsic_checkpoint": intrinsic},
            "info": {"roi_check": (intrinsic - fee - prem) / prem}}

"""H078 (decimal, usd): maximum exposure under a parametric VaR budget.

The reading, clause by clause:
* VaR budget V, daily volatility sigma, confidence multiplier z, holding period
  h (days).
* "Under square-root-of-time scaling": horizon volatility = sigma * sqrt(h).
  This is the slot horizon_volatility_checkpoint ("volatility scaled to the
  holding horizon", a ratio).
* Parametric VaR = exposure * z * sigma * sqrt(h).  "maximum portfolio exposure
  that keeps parametric VaR within the budget": VaR <= V ("within" is <=), so
  the maximum is exposure = V / (z * sigma * sqrt(h)).
* sqrt uses hlib.sqrt, which is exact for perfect-square holding periods and is
  flagged non_rational otherwise.
"""
from hlib import num, sqrt

KEY = "H078"


def solve(b):
    budget = num(b, "permits a VaR budget of {N}")
    sigma, z, h = num(b, "daily volatility {N}, uses confidence multiplier {N}, and is held for {N}")
    hvol = sigma * sqrt(h)
    return {"final": budget / (z * hvol),
            "slots": {"horizon_volatility_checkpoint": hvol}}

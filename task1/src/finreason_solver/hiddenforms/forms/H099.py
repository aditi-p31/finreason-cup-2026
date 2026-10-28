"""H099 (decimal, usd): pre-shock price from current price after loss then rebound.

The reading, clause by clause:
* Current price P_now "after a global shock reduced its pre-shock price by loss
  ratio L": post-shock = P0 * (1 - L).
* "increased the resulting post-shock price by a rebound ratio equal to q times
  the shock loss ratio": rebound ratio rho = q * L (slot
  rebound_ratio_checkpoint), so P_now = P0 * (1 - L) * (1 + rho).
* "Apply the loss and rebound sequentially": P0 = P_now / ((1 - L) * (1 + rho)).
"""
from hlib import num

KEY = "H099"


def solve(b):
    p_now = num(b, "currently priced at {N} USD per token")
    loss = num(b, "reduced its pre-shock price by loss ratio {N}")
    q = num(b, "rebound ratio equal to {N} times the shock loss ratio")
    rho = q * loss
    return {"final": p_now / ((1 - loss) * (1 + rho)),
            "slots": {"rebound_ratio_checkpoint": rho}}

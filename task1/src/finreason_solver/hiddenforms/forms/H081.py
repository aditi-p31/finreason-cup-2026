"""H081 (decimal, percent): feasible Strategy A weight endpoint.

The reading, clause by clause:
* B: upside rate uB, downturn loss lB.  A: upside uA = uB + inc_up, downturn loss
  lA = lB + inc_loss.  Downturn probability p, upside probability 1 - p.
* portfolio upside ending value = K[w(1 + uA) + (1 - w)(1 + uB)] >= U gives the
  lower endpoint w_lo = (U/K - 1 - uB) / inc_up.
* portfolio downturn ending value = K[w(1 - lA) + (1 - w)(1 - lB)] >= D gives the
  upper endpoint w_hi = (1 - lB - D/K) / inc_loss.
* all-A probability-weighted ending value EA = (1 - p) K(1 + uA) + p K(1 - lA);
  all-B EB likewise.  EA > EB (strict) -> upper endpoint; otherwise, including an
  exact tie, the lower endpoint.
* feasibility (0 < w_lo <= w_hi < 1) is checked and recorded in info.
* report the selected w x 100 (percent).
Slots:
* strategy_a_weighted_upside_checkpoint = (1 - p) x K(1 + uA), the upside term of
  the all-A probability-weighted ending value.
* strategy_b_downturn_checkpoint = K(1 - lB), Strategy B's (all-capital) ending
  value in the downturn.
"""
from hlib import num

KEY = "H081"


def solve(b):
    k = num(b, "allocates weight w of capital {N} to Strategy A")
    p = num(b, "The downturn probability is {N}, with")
    ub, lb = num(b, "Strategy B earns upside return {N} and loses {N} in the downturn.")
    inc_up = num(b, "plus positive incremental return {N}, but")
    inc_loss = num(b, "plus positive incremental loss {N};")
    up_req, down_req = num(b, "must end with at least {N} in the upside scenario and at least {N} in the downturn.")
    ua = ub + inc_up
    la = lb + inc_loss
    w_lo = (up_req / k - 1 - ub) / inc_up
    w_hi = (1 - lb - down_req / k) / inc_loss
    a_up, a_down = k * (1 + ua), k * (1 - la)
    b_up, b_down = k * (1 + ub), k * (1 - lb)
    ev_a = (1 - p) * a_up + p * a_down
    ev_b = (1 - p) * b_up + p * b_down
    w = w_hi if ev_a > ev_b else w_lo
    feasible = 0 < w_lo <= w_hi < 1 and ua < 1 and la < 1
    return {"final": w * 100,
            "slots": {"strategy_a_weighted_upside_checkpoint": (1 - p) * a_up,
                      "strategy_b_downturn_checkpoint": b_down},
            "info": {"w_lo": w_lo, "w_hi": w_hi, "ev_a": ev_a, "ev_b": ev_b,
                     "feasible": feasible, "ev_margin": ev_a - ev_b}}

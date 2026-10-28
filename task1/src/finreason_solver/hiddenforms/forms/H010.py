"""H010 (decimal, percent): required joint success probability as a share of the Frechet band.

The reading, clause by clause:
* Cost-synergy: marginal probability p_c, benefit B_c when it succeeds.
  Revenue-synergy: marginal probability p_r, benefit B_r when it succeeds.
* "If both initiatives succeed, incremental benefit I is earned beyond the
  standalone benefits", so expected gross benefit =
  p_c * B_c + p_r * B_r + q * I, with q the joint success probability.
* "Unconditional integration cost K" is deducted once:
  expected net benefit = p_c B_c + p_r B_r + q I - K.
* "Solve for the joint success probability needed to meet the target" T:
  set the expected net benefit equal to T, so
  q = (T + K - p_c B_c - p_r B_r) / I.
* Frechet lower bound L = p_r - (1 - p_c) (as the text defines it), upper
  bound U = p_r, band width W = 1 - p_c (text), which equals U - L.
* Final: "percentage of this feasible band consumed above its lower bound by
  the required joint success probability" = (q - L) / W * 100 (unit percent).
  The text says a result above 100 percent is infeasible but is still the
  value to report, so no clamp.
Slots:
* gross_requirement_checkpoint: "gross expected benefit required before the
  integration cost is deducted" = T + K (USD millions, no rescale; the text
  already states USD millions).
* frechet_lower_bound_checkpoint: L = p_r - (1 - p_c) (ratio).
"""
from hlib import num

KEY = "H010"


def solve(b):
    pc, bc = num(b, "The cost-synergy initiative has marginal success probability {N} and contributes {N} USD millions whenever it succeeds.")
    pr, br = num(b, "The revenue-synergy initiative has marginal success probability {N} and contributes {N} USD millions whenever it succeeds.")
    inc = num(b, "incremental benefit {N} USD millions is earned beyond the standalone benefits")
    cost = num(b, "Unconditional integration cost is {N} USD millions")
    target = num(b, "required expected net benefit is {N} USD millions")
    gross_req = target + cost
    q = (gross_req - pc * bc - pr * br) / inc
    lower = pr - (1 - pc)
    upper = pr
    width = 1 - pc
    share = (q - lower) / width * 100
    return {
        "final": share,
        "slots": {
            "gross_requirement_checkpoint": gross_req,
            "frechet_lower_bound_checkpoint": lower,
        },
        "info": {"joint_q": q, "lower": lower, "upper": upper, "width": width,
                 "upper_minus_lower": upper - lower},
    }

"""H087 (decimal, percent): share of expected integration benefit from the joint term.

The reading:
  expected cost benefit    = p_cost * B_cost      -> slot expected_cost_benefit_checkpoint
  expected revenue benefit = p_rev * B_rev        -> slot expected_revenue_benefit_checkpoint
  independence: P(both) = p_cost * p_rev; expected joint = p_cost * p_rev * J
  total expected gross benefit = cost + revenue + joint (joint is "beyond the two
  standalone benefits").
  answer = expected joint / total * 100 (percent).
Amounts are already in USD millions.
"""
from hlib import num

KEY = "H087"


def solve(b):
    pc, bc = num(b, "The cost-synergy initiative succeeds with marginal probability {N} and contributes {N} USD millions whenever it succeeds")
    pr, br = num(b, "The revenue-synergy initiative succeeds with marginal probability {N} and contributes {N} USD millions whenever it succeeds")
    j = num(b, "they also create incremental joint benefit {N} USD millions beyond")
    ec = pc * bc
    er = pr * br
    ej = pc * pr * j
    total = ec + er + ej
    return {"final": ej / total * 100,
            "slots": {"expected_cost_benefit_checkpoint": ec,
                      "expected_revenue_benefit_checkpoint": er},
            "info": {"expected_joint": ej, "total": total}}

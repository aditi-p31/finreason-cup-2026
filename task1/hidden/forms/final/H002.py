"""H002 (decimal, usd): loss-severity alignment of state-specific reimbursement.

The reading, clause by clause:
* Three mutually exclusive, exhaustive states.  P(minor) = p_minor as stated.
  "Conditional on the minor state not occurring, the moderate state has
  probability q" gives P(moderate) = (1 - p_minor) * q.  "otherwise the severe
  state occurs" gives P(severe) = 1 - P(minor) - P(moderate)
  (= (1 - p_minor) * (1 - q)).
* Gross losses L_i and reimbursement fractions r_i in the stated order
  minor, moderate, severe.
* Actual expected reimbursement = sum_i P_i * r_i * L_i.
* Probability-weighted mean reimbursement rate = sum_i P_i * r_i (the P_i sum
  to 1, so no renormalisation).  Expected gross loss = sum_i P_i * L_i.
  Flat-rate benchmark = mean rate * expected gross loss.
* Final = actual - benchmark, in USD, signed (the text says a negative result
  is meaningful), so no clamp.
Slots: moderate_weighted_loss = P(moderate) * L_moderate;
severe_weighted_loss = P(severe) * L_severe ("probability-weighted ...
gross loss", i.e. before any reimbursement fraction).
"""
from hlib import num

KEY = "H002"


def solve(b):
    p_minor = num(b, "The minor state has probability {N}.")
    q_mod = num(b, "Conditional on the minor state not occurring, the moderate state has probability {N};")
    l1, l2, l3 = num(b, "Their gross fraud losses are {N}, {N}, and {N} USD")
    r1, r2, r3 = num(b, "the account reimburses fractions {N}, {N}, and {N}.")
    p1 = p_minor
    p2 = (1 - p_minor) * q_mod
    p3 = 1 - p1 - p2
    actual = p1 * r1 * l1 + p2 * r2 * l2 + p3 * r3 * l3
    mean_rate = p1 * r1 + p2 * r2 + p3 * r3
    exp_loss = p1 * l1 + p2 * l2 + p3 * l3
    benchmark = mean_rate * exp_loss
    return {
        "final": actual - benchmark,
        "slots": {
            "moderate_weighted_loss_checkpoint": p2 * l2,
            "severe_weighted_loss_checkpoint": p3 * l3,
        },
        "info": {"p": [p1, p2, p3], "actual": actual, "mean_rate": mean_rate,
                 "expected_loss": exp_loss, "benchmark": benchmark},
    }

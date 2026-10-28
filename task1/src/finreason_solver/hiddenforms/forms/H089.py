"""H089 (decimal, dimensionless): minimum additional KYC control credit.

The reading, clause by clause:
* Source-of-funds score S, jurisdiction score J, existing credit E, ceiling C,
  all on one additive scale; credits reduce residual risk one-for-one.
* Residual = S + J - E - x, with x the additional credit, x >= 0 ("additional
  credit cannot be negative").
* "no greater than the residual-risk ceiling": S + J - E - x <= C, so the
  minimum x = max(S + J - E - C, 0).
* Final: x in risk-score points.
Slot combined_risk_checkpoint: "combined source-of-funds and jurisdiction risk
score" = S + J.
"""
from hlib import num, pos

KEY = "H089"


def solve(b):
    s, j, e, c = num(b, "A customer has source-of-funds risk score {N}, jurisdiction risk score {N}, existing verified-control credit {N}, and standard residual-risk ceiling {N}.")
    combined = s + j
    gap = combined - e - c
    return {
        "final": pos(gap),
        "slots": {"combined_risk_checkpoint": combined},
        "info": {"unfloored_gap": gap, "residual_before_additional": combined - e},
    }

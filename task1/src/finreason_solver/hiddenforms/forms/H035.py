"""H035 (decimal, usd): post-shock crypto price under severe or mild policy.

The reading:
* post-shock price = start * (1 - loss fraction).
* "The severe policy applies when that loss ratio is at least T" -> severe if
  loss >= T (inclusive, "at least"); otherwise mild.
* severe: post * (1 + support_severe) - deduction_severe.
* mild:   post * (1 + support_mild)   - deduction_mild.
  ("increases the post-shock price by support ratio s and then deducts d")
Slot: share of the initial price retained after the shock = 1 - loss fraction
(ratio).
"""
from hlib import num

KEY = "H035"


def solve(b):
    p0, loss = num(b, "starts at {N} USD per token and loses fraction {N} of its price")
    thr = num(b, "applies when that loss ratio is at least {N};")
    s_sev, d_sev = num(b, "the severe policy increases the post-shock price by support ratio {N} and then deducts {N} USD per token")
    s_mild, d_mild = num(b, "The mild policy increases it by support ratio {N} and then deducts {N} USD per token")

    retained = 1 - loss
    post = p0 * retained
    severe = loss >= thr
    net = post * (1 + s_sev) - d_sev if severe else post * (1 + s_mild) - d_mild
    return {
        "final": net,
        "slots": {"post_shock_retention_checkpoint": retained},
        "info": {"severe": severe, "loss_minus_threshold": loss - thr,
                 "post_shock_price": post},
    }

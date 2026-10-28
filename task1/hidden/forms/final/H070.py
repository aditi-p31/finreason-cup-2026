"""H070 (decimal, usd): gross transfer needed for an exact net receipt.

The reading, clause by clause:
* Forward stages: proportional fee ratio f, then fixed network fee k, then a
  rebate r is credited: net = G * (1 - f) - k + r.
* Target net receipt N.  "Reverse the stages in order by removing the rebate,
  restoring the fixed fee, and dividing by the proportional-fee retention
  ratio": G = (N - r + k) / (1 - f).
* Final: G in USD.
Slot pre_rebate_checkpoint: "receipt required before applying the rebate"
= N - r (USD).
"""
from hlib import num

KEY = "H070"


def solve(b):
    fee, fixed, rebate = num(b, "A transfer is charged a proportional fee ratio of {N} and then a fixed network fee of {N} USD, after which a rebate of {N} USD is credited.")
    target = num(b, "for the recipient to obtain exactly {N} USD")
    pre_rebate = target - rebate
    after_fixed_restored = pre_rebate + fixed
    gross = after_fixed_restored / (1 - fee)
    check = gross * (1 - fee) - fixed + rebate
    return {
        "final": gross,
        "slots": {"pre_rebate_checkpoint": pre_rebate},
        "info": {"after_fixed_restored": after_fixed_restored,
                 "forward_check_minus_target": check - target},
    }

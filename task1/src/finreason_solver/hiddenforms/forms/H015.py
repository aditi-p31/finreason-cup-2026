"""H015 (decimal, usd_million): ratcheted dividend limit versus liquidity cap.

The reading, clause by clause:
* distributable earnings = forecast net income - the amount that "must first
  retain" (both in USD millions).
* authorization starts at 100% and passes three sequential ratchet stages, each
  reducing the remaining share by the same fraction t, so the policy limit is
  distributable earnings * (1 - t)^3 (the question states this formula).
* the liquidity plan separately caps the cash dividend at a stated amount.
* "maximum total cash dividend satisfying both limits" = min(policy limit, cap).
  No rounding before the final; units stay USD millions.

Slot one_stage_payout_factor_checkpoint: "authorized payout share remaining after
one ratchet stage" = 1 * (1 - t) = 1 - t (a ratio, starting share 100% = 1).
"""
from hlib import num, ipow

KEY = "H015"


def solve(b):
    ni, retain = num(b, "forecasts net income of {N} and must first retain {N},")
    t = num(b, "by the same fraction t={N},")
    cap = num(b, "caps the cash dividend at {N}.")
    distributable = ni - retain
    one_stage = 1 - t
    policy_limit = distributable * ipow(one_stage, 3)
    final = min(policy_limit, cap)
    return {
        "final": final,
        "slots": {"one_stage_payout_factor_checkpoint": one_stage},
        "info": {"distributable": distributable, "policy_limit": policy_limit, "cap": cap},
    }

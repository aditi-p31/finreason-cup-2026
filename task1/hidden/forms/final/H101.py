"""H101 (enum): three-stage compliance risk reduction plan choice.

The reading, clause by clause:
* residual risk of a plan = inherent risk * (1 - per-stage reduction)^3
  ("multiply inherent risk by one minus that plan's per-stage fraction three
  successive times").
* net cost = (implementation + monitoring) * (1 - credit fraction).
* qualifies iff residual <= risk cap ("no more than") and net cost <= cost cap
  ("no more than").
* both qualify -> lower exact net cost, Plan A on an exact tie; exactly one ->
  that one; none -> "Neither plan".
Slot plan_a_residual_factor_checkpoint: "Plan A's retained-risk factor after
one of the three identical sequential reduction stages" = 1 - Plan A's
per-stage reduction (the one-stage multiplier, not inherent risk times it:
"one-stage retained-risk factor").
"""
from hlib import num, ipow, pick_two

KEY = "H101"


def solve(b):
    inh = num(b, "Inherent risk is {N}.")
    ra, ia, ma, ca = num(b, "Plan A has per-stage fractional risk reduction {N}, implementation cost {N} USD, monitoring cost {N} USD, and fractional cost credit {N}.")
    rb, ib, mb, cb = num(b, "Plan B has per-stage fractional risk reduction {N}, implementation cost {N} USD, monitoring cost {N} USD, and fractional cost credit {N}.")
    rcap, ccap = num(b, "A plan qualifies only if residual risk is no more than {N} and net cost is no more than {N} USD.")

    res_a = inh * ipow(1 - ra, 3)
    res_b = inh * ipow(1 - rb, 3)
    net_a = (ia + ma) * (1 - ca)
    net_b = (ib + mb) * (1 - cb)
    ok_a = res_a <= rcap and net_a <= ccap
    ok_b = res_b <= rcap and net_b <= ccap
    label = pick_two(ok_a, ok_b, net_a, net_b, a="Plan A", b="Plan B",
                     neither="Neither plan", better="lower", tie="Plan A")
    return {"final": label,
            "slots": {"plan_a_residual_factor_checkpoint": 1 - ra},
            "info": {"res_a": res_a, "res_b": res_b, "net_a": net_a, "net_b": net_b,
                     "risk_cap": rcap, "cost_cap": ccap, "ok_a": ok_a, "ok_b": ok_b}}

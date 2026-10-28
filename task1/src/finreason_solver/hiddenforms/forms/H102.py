"""H102 (decimal, usd): extra stake in a second pool to reach a net annual reward.

The reading, clause by clause:
* Existing position E earns yield ratio y1 over the one annual period:
  existing reward = E * y1.
* The second pool pays y2 on the added stake S: S * y2.
* A fixed annual fee Fee is deducted once and does not depend on S.
* Net annual reward = E * y1 + S * y2 - Fee = target.
* S = (target + Fee - E * y1) / y2.
Slot: existing_reward_checkpoint = E * y1 (usd).
"""
from hlib import num

KEY = "H102"


def solve(b):
    e, y1 = num(b, "a DeFi user already has {N} USD earning yield ratio {N}.")
    y2 = num(b, "A second pool offers yield ratio {N}.")
    fee = num(b, "charges a fixed annual fee of {N} USD")
    target = num(b, "deliver a net annual reward of {N} USD.")
    existing = e * y1
    stake = (target + fee - existing) / y2
    return {
        "final": stake,
        "slots": {"existing_reward_checkpoint": existing},
        "info": {"gap_to_fill": target + fee - existing},
    }

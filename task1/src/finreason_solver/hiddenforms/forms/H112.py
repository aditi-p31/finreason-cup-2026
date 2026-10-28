"""H112 (decimal, usd): DeFi liquidity position with a conditional hedge.

The reading, clause by clause:
* Capital C, fee-yield ratio f, impermanent-loss ratio l.
  Fee income = C * f; unhedged loss = C * l.
* "An optional hedge covers h of that loss and, only when activated, costs c
  of capital": covered loss = h * C * l; hedge cost = c * C (only if active).
* "If the exact unhedged loss strictly exceeds the risk limit Lim, activate
  the hedge": activate iff C * l > Lim (strict); otherwise unhedged, no cost.
* Net P/L excluding return of capital:
  hedged   = C f - C l + h C l - c C
  unhedged = C f - C l
* Final: the selected net P/L in USD.
Slot covered_loss_ratio_checkpoint: "covered impermanent loss as a ratio of
position capital" = h * l.  The text states the coverage ("covers h of that
loss") unconditionally and puts "only when activated" on the cost alone, and
the slot, unlike the final, does not say "selected", so it is h * l on every
draw.
"""
from hlib import num

KEY = "H112"


def solve(b):
    cap, fy, il = num(b, "a DeFi liquidity position has capital of {N} USD, earns fee-yield ratio {N}, and incurs impermanent-loss ratio {N}.")
    cover, cost_r = num(b, "An optional hedge covers {N} of that loss and, only when activated, costs {N} of capital.")
    limit = num(b, "strictly exceeds the risk limit of {N} USD")
    fee_income = cap * fy
    loss = cap * il
    covered_ratio = cover * il
    unhedged = fee_income - loss
    hedged = fee_income - loss + covered_ratio * cap - cost_r * cap
    active = loss > limit
    return {
        "final": hedged if active else unhedged,
        "slots": {"covered_loss_ratio_checkpoint": covered_ratio},
        "info": {"unhedged_loss": loss, "limit": limit, "hedge_active": active,
                 "loss_minus_limit": loss - limit,
                 "net_hedged": hedged, "net_unhedged": unhedged},
    }

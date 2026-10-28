"""H004 (decimal, usd): net stress reserve after recovery.

The reading, clause by clause:
* market stress loss = portfolio value x market shock ratio x loss sensitivity
  ("market shock ratio m with loss sensitivity s").
* liquidity loss = portfolio value x liquidity shock ratio ("applied directly to
  portfolio value", so no sensitivity).
* gross stress loss = market loss + liquidity loss ("the combined gross loss").
* recoverable amount = recovery ratio x gross loss.
* net reserve = gross loss - recoverable amount.
Slot market_loss_checkpoint = the market stress dollar loss = V x m x s.
A recovery ratio of 1 genuinely gives a net reserve of exactly 0.
"""
from hlib import num

KEY = "H004"


def solve(b):
    v = num(b, "A portfolio worth {N} faces")
    m, s = num(b, "market shock ratio {N} with loss sensitivity {N},")
    liq = num(b, "plus liquidity shock ratio {N} applied directly to portfolio value")
    rec = num(b, "expects to recover ratio {N} of the combined gross loss")
    market_loss = v * m * s
    liq_loss = v * liq
    gross = market_loss + liq_loss
    recoverable = rec * gross
    net = gross - recoverable
    return {"final": net,
            "slots": {"market_loss_checkpoint": market_loss},
            "info": {"liquidity_loss": liq_loss, "gross": gross, "recoverable": recoverable}}

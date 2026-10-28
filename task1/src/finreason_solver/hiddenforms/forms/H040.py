"""H040 (decimal, dimensionless): maximum token emission under a market-cap ceiling.

The reading, clause by clause:
* Outstanding supply U today; the burn of B units leaves U - B.
* Expected post-burn price P, unchanged by further emission.
* Total market cap "must not exceed" the ceiling K: supply * P <= K.
* "first compute the market cap of the current supply at that expected price":
  U * P.  "Current supply" is the supply the token "has" now (the burn is
  stated in the future tense, "will burn"), so U, not U - B.
* "express it as a multiple of the ceiling": m = U * P / K.
* "use that multiple to recover the ceiling-compatible total supply":
  U / m = K / P.
* Maximum additional units emitted after the burn = K / P - (U - B).
  The recipe states no floor at zero, so the difference is returned as is
  (the final value is identical under the U or U - B reading of "current
  supply"; only the slot depends on it).
Slot: ceiling_utilization_checkpoint = m = U * P / K (unit multiple).

Adjudication (batch 1, 2026-09-27): readers A and B agreed on the final on all
three draws and differed only on this slot (B used U - B as "current supply").
Adopted reader A's reading.  The text marks every post-burn state explicitly
("After the burn, the token is expected to trade", "emitted after the burn")
but says "the current supply" here, and the token "has" U units now while it
"will burn" B.  The slot calls the result a "benchmark" market cap, which fits
a reference valuation of today's supply at the expected price rather than an
actual post-burn market cap.  No rounding-boundary signal in the draws
separates the two readings, so the slot is a judgment call; the final is
unaffected.  Draw 3 is already over the ceiling after the burn (925 * 2 > K),
and with no stated floor at zero the negative difference is kept.
"""
from hlib import num

KEY = "H040"


def solve(b):
    units, burn = num(b, "A token has {N} units outstanding and will burn {N} units.")
    price = num(b, "expected to trade at {N} USD per unit")
    ceiling = num(b, "total market capitalization must not exceed {N} USD")
    mcap_current = units * price
    multiple = mcap_current / ceiling
    total_supply = units / multiple
    post_burn = units - burn
    extra = total_supply - post_burn
    return {
        "final": extra,
        "slots": {"ceiling_utilization_checkpoint": multiple},
        "info": {"mcap_current": mcap_current, "ceiling_supply": total_supply,
                 "post_burn_supply": post_burn, "post_burn_multiple": post_burn * price / ceiling},
    }

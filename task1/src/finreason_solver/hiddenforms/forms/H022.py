"""H022 (decimal, percent): target sellers' post-earnout ownership.

The reading, clause by clause:
* all shares are issued at one fixed, unchanged price, so share counts are
  proportional to values and the price cancels.
* upfront stock consideration = base consideration x (1 - cash fraction)
  ("0.2 of that base is paid in cash and the remainder in acquirer common shares").
* the earnout settlement value is incremental and fully in shares.
* sellers' shares (in value) = upfront stock + earnout; total base = predeal
  equity value + upfront stock + earnout (no other issuance or disposal).
* ownership = sellers / total, reported as a percentage (x 100).
Slot upfront_stock_consideration_checkpoint = base x (1 - cash fraction), in the
same money units as the text (spec unit usd_million, no rescaling).
"""
from hlib import num

KEY = "H022"


def solve(b):
    pre = num(b, "have aggregate reference equity value {N} at one fixed")
    base = num(b, "Upfront base consideration is {N}, excluding the earnout")
    cash = num(b, "excluding the earnout; {N} of that base is paid in cash")
    earn = num(b, "earnout with settlement value {N}, incremental")
    upfront_stock = base * (1 - cash)
    sellers = upfront_stock + earn
    total = pre + sellers
    return {"final": sellers / total * 100,
            "slots": {"upfront_stock_consideration_checkpoint": upfront_stock},
            "info": {"sellers_value": sellers, "total_value": total}}

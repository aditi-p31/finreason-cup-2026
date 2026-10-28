"""H057 (decimal, percent): unit gross-profit retention after discount and cost change.

The reading, clause by clause:
* Original unit price P; baseline gross margin ratio m "calculated from that
  same undiscounted unit price", so baseline unit gross profit = P * m.
* "the selling price is discounted by d of the original price": new price =
  P - d * P = P * (1 - d).  This is the slot discounted_unit_price_checkpoint
  ("discounted selling price per unit before subtracting unit cost").
* "post-change unit cost is c": new unit gross profit = P * (1 - d) - c.
* "What percentage of the original per-unit gross profit is retained":
  final = (P * (1 - d) - c) / (P * m) * 100, a percentage (x 100), not the
  post-change margin.  The slot is not fed downstream in rounded form.
"""
from hlib import num

KEY = "H057"


def solve(b):
    price = num(b, "original unit price is {N} USD")
    margin = num(b, "baseline gross margin ratio is {N}, calculated")
    disc = num(b, "the selling price is discounted by {N} of the original price")
    cost = num(b, "the post-change unit cost is {N} USD")
    base_gp = price * margin
    new_price = price * (1 - disc)
    new_gp = new_price - cost
    return {"final": new_gp / base_gp * 100,
            "slots": {"discounted_unit_price_checkpoint": new_price},
            "info": {"baseline_unit_gp": base_gp, "new_unit_gp": new_gp}}

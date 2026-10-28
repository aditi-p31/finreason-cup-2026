"""H011 (decimal, percent): net economic exposure percentage.

The reading, clause by clause as the question states it:
  derivative_equivalent = derivative reference shares * delta
  "add all long exposure"  -> + direct long shares + attributed shares
  "subtract the short hedge" -> - offsetting short shares
  "divide the signed result by shares outstanding" -> ratio
  "convert the ratio to a percentage" -> * 100
Slot derivative_equivalent_checkpoint ("delta-adjusted derivative-equivalent
shares", unit count) = derivative reference shares * delta.
No comparisons or tie rules in this template.
"""
from hlib import num

KEY = "H011"


def solve(b):
    direct = num(b, "an investor has {N} direct long shares")
    attributed = num(b, "{N} shares attributed through related holdings")
    deriv, delta = num(b, "derivative notional equivalent to {N} shares with exposure delta {N}.")
    short = num(b, "The investor also has {N} shares of offsetting short exposure")
    outstanding = num(b, "The issuer has {N} shares outstanding")
    deq = deriv * delta
    signed = deq + direct + attributed - short
    ratio = signed / outstanding
    return {"final": ratio * 100,
            "slots": {"derivative_equivalent_checkpoint": deq},
            "info": {"signed_exposure_shares": signed, "ratio": ratio}}

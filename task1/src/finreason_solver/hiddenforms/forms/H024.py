"""H024 (decimal, usd): maximum preferred dividend per current share.

The reading:
* Earnings per current share before preferred distributions = E.
* The issuance multiplies the share base by (1 + ratio).
* Pro forma post-issuance EPS = (E - pref) / (1 + ratio), where pref is the
  preferred-dividend allocation per current common share.
* "at or above" floor is inclusive, so the maximum pref solves
  (E - pref) / (1 + ratio) = floor: pref = E - floor x (1 + ratio).
Slot dilution_multiple_checkpoint = 1 + ratio (post-issuance share-base multiple).
"""
from hlib import num

KEY = "H024"


def solve(b):
    e = num(b, "earnings normalized per current common share are {N}.")
    r = num(b, "increases the common-share base by ratio {N}.")
    floor = num(b, "post-issuance EPS at or above {N},")
    mult = 1 + r
    pref = e - floor * mult
    return {"final": pref,
            "slots": {"dilution_multiple_checkpoint": mult}}

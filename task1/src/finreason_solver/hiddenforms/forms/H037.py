"""H037 (decimal, usd): minimum aggregate coupon cash for a target holding return.

The reading, clause by clause:
* total acquisition outlay O = clean price P + settlement cost S (settlement
  cost already includes accrued interest and fees; nothing is added again).
* holding-period return = (coupon cash C + redemption cash R - O) / O.
* "minimum aggregate coupon cash that exactly meets target return ratio t":
  the return is increasing in C, so the minimum C meeting the target is the
  one where the return equals t exactly: C = O * (1 + t) - R.
  (All three draws give a positive C, so no floor at zero is exercised.)

Slot acquisition_outlay_checkpoint "clean price plus all additional
acquisition cash" = P + S.
"""
from hlib import num

KEY = "H037"


def solve(b):
    price, redemption = num(b, "A bond has quoted clean price {N} and will pay redemption cash {N} "
                               "over the planned holding period.")
    settle = num(b, "The investor also pays settlement cost {N}, defined as")
    target = num(b, "exactly meets target return ratio {N},")
    outlay = price + settle
    coupon = outlay * (1 + target) - redemption
    return {
        "final": coupon,
        "slots": {"acquisition_outlay_checkpoint": outlay},
        "info": {"outlay": outlay, "check_return": (coupon + redemption - outlay) / outlay},
    }

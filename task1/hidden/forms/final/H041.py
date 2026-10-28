"""H041 (decimal, usd): second-period payment hitting a target balance.

The reading, clause by clause:
* interest is applied before each end-of-period payment, same effective rate r
  in both periods.
* balance after first payment B1 = P0 x (1 + r) - payment1.
* second period: B1 x (1 + r) - x = target balance, so x = B1 x (1 + r) - target.
Slot first_payment_balance_checkpoint = B1.
"""
from hlib import num

KEY = "H041"


def solve(b):
    p0 = num(b, "starts with an outstanding principal of {N}.")
    r = num(b, "use the same effective rate of {N},")
    pay1 = num(b, "The borrower pays {N} at the end of the first period")
    target = num(b, "leaves a balance of {N} immediately after that payment")
    b1 = p0 * (1 + r) - pay1
    x = b1 * (1 + r) - target
    return {"final": x,
            "slots": {"first_payment_balance_checkpoint": b1},
            "info": {"balance_before_second_payment": b1 * (1 + r)}}

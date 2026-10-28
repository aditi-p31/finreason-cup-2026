"""H085 (decimal, usd): signed two-period ending-balance difference, current minus refinance.

The reading:
* Both paths start from the same outstanding principal P.
* Current loan: each period B <- B x (1 + r_c) - pay_c ("Interest accrues
  before each payment"), two periods from P.
* Refinance: opening balance = P + fee (fee capitalized), then each period
  B <- B x (1 + r_r) - pay_r, two periods.
* Answer = current ending balance after period 2 - refinance ending balance
  after period 2, signed.
Slots: each path's balance after its first payment (end of period 1).
"""
from hlib import num

KEY = "H085"


def solve(b):
    p = num(b, "Both paths start from outstanding principal of {N}.")
    rc, payc = num(b, "The current loan uses an effective rate of {N} and a payment of {N} at each period end.")
    fee = num(b, "The refinance capitalizes a fee of {N} into its opening balance")
    rr, payr = num(b, "then uses an effective rate of {N} and a payment of {N} at each period end.")
    c1 = p * (1 + rc) - payc
    c2 = c1 * (1 + rc) - payc
    f0 = p + fee
    f1 = f0 * (1 + rr) - payr
    f2 = f1 * (1 + rr) - payr
    return {"final": c2 - f2,
            "slots": {"current_first_payment_balance_checkpoint": c1,
                      "refinance_first_payment_balance_checkpoint": f1},
            "info": {"current_end2": c2, "refinance_end2": f2}}

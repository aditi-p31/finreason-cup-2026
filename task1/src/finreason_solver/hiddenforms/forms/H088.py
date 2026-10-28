"""H088 (decimal, usd): merchant net settlement.

Reading:
* variable fee = rate * gross sales ("rate r on those gross sales").
* fixed fee = per-transaction fee * transaction count.
* chargebacks C are included in gross sales and fraction phi is recovered, so
  the unrecovered chargeback loss = C * (1 - phi).
* reserve withheld R.
* net = gross - variable fee - fixed fee - unrecovered chargebacks - reserve,
  exactly the four deductions the question lists.
* Slots: variable_fee_checkpoint = rate * gross; fixed_fee_checkpoint =
  per-transaction fee * count; chargeback_loss_checkpoint = C * (1 - phi).
"""
from hlib import num

KEY = "H088"


def solve(b):
    gross, n = num(b, "gross sales before chargebacks of {N} across {N} transactions.")
    rate, per_tx = num(b, "The processor charges rate {N} on those gross sales plus {N} per transaction.")
    cb, frac = num(b, "Chargebacks included in the gross-sales amount total {N}, of which fraction {N} is recovered.")
    reserve = num(b, "The processor also withholds reserve {N}.")
    var_fee = rate * gross
    fixed_fee = per_tx * n
    cb_loss = cb * (1 - frac)
    net = gross - var_fee - fixed_fee - cb_loss - reserve
    return {"final": net,
            "slots": {"variable_fee_checkpoint": var_fee,
                      "fixed_fee_checkpoint": fixed_fee,
                      "chargeback_loss_checkpoint": cb_loss}}

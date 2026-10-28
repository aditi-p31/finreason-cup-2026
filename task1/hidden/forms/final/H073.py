"""H073 (decimal, usd): binding quoted purchase price for a target total return.

The reading, clause by clause:
* net terminal receipts = gross terminal sale proceeds + holding-period
  dividend cash - exit cost.  Dividends are cash received over the holding
  period and are part of a total return ("Ignore ... dividend reinvestment"
  removes only reinvestment, not the dividend cash itself).
* complete acquisition outlay = quote + entry cost.
* total return = (net receipts - outlay) / outlay; set equal to the target
  ratio (given as a ratio: "0.20 means 20%").
  => outlay = net receipts / (1 + target); quote = outlay - entry cost.
* The final is the exact threshold; run_forms rounds half up to cents.
Slot net_receipts_checkpoint: "expected terminal receipts after exit cost" =
proceeds + dividends - exit cost (the slot is rounded to cents by run_forms).

Adjudication (batch 9, 2026-09-27): readers agreed on every final and differed
only on this slot (A: gross + dividends - exit = 100.45 / 87.73 / 86.82;
B: gross - exit before dividends = 80 / 78 / 77).  Reader A's reading is kept.
(1) The slot id is net_receipts_checkpoint, and the only receipts quantity the
text defines is "net terminal receipts", the numerator of the stated total
return.  Both readers' finals use gross + dividends - exit for that
numerator, so the checkpoint is that same quantity.  (2) The slot says
"terminal receipts" (the text's term for the return numerator), not "sale
proceeds", which is the text's term for the 89 / 88 figure.  (3) The slot is
"rounded half up to cents".  With the three-decimal dividend cash, A's value
is 100.445 on draw 1, an exact half-cent tie, and 86.822 on draw 3.  Under B's
reading the value is a whole number on all three draws, so the stated rounding
would never matter.
"""
from hlib import num

KEY = "H073"


def solve(b):
    gross, div = num(b, "gross terminal sale proceeds {N} and holding-period dividend cash {N}.")
    exit_c, entry_c = num(b, "Selling incurs exit cost {N}, while buying incurs entry cost {N} in addition")
    tgt = num(b, "For target ratio {N}, where")

    net = gross + div - exit_c
    outlay = net / (1 + tgt)
    quote = outlay - entry_c
    return {"final": quote,
            "slots": {"net_receipts_checkpoint": net},
            "info": {"outlay": outlay,
                     "check_return": (net - outlay) / outlay}}

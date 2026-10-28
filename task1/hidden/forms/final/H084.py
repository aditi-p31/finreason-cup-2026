"""H084 (decimal, multiple): degree of financial leverage from two tranches.

The reading:
* Interest A = debt A x rate A; interest B = debt B x rate B (same period).
* EBIT = earnings before tax + interest A + interest B.
* DFL = EBIT / earnings before tax.
Slots: tranche_a_interest_checkpoint = interest A, tranche_b_interest_checkpoint
= interest B (exact, rounded independently by run_forms).
"""
from hlib import num

KEY = "H084"


def solve(b):
    ebt = num(b, "positive earnings before tax of {N} USD")
    da, ra = num(b, "Tranche A debt is {N} USD at rate {N},")
    db, rb = num(b, "tranche B debt is {N} USD at rate {N}.")
    ia = da * ra
    ib = db * rb
    ebit = ebt + ia + ib
    return {"final": ebit / ebt,
            "slots": {"tranche_a_interest_checkpoint": ia,
                      "tranche_b_interest_checkpoint": ib},
            "info": {"ebit": ebit}}

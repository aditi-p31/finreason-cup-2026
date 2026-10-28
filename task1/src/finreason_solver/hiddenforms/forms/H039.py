"""H039 (decimal, usd_million): equity injection to hit a D/E ceiling.

The reading:
* Debt after both actions = debt + borrowing - repayment.
* "minimum new equity injection ... so that the debt-to-equity ratio equals
  the permitted ceiling k": (debt + borrowing - repayment) / (equity + X) = k,
  so X = (debt + borrowing - repayment) / k - equity.  The text states an
  equality, so no clamp at zero is applied (all draws give a positive X
  anyway; see info).
* Amounts are already in USD millions; no rescaling.
Slot debt_after_borrowing_checkpoint = debt + borrowing (after the planned
borrowing, before the repayment).
"""
from hlib import num

KEY = "H039"


def solve(b):
    debt, equity = num(b, "current debt of {N} and current equity of {N}.")
    borrow, repay = num(b, "additional borrowing of {N} and a debt repayment of {N}.")
    ceiling = num(b, "equals the permitted ceiling {N}.")
    after_borrow = debt + borrow
    debt_final = after_borrow - repay
    x = debt_final / ceiling - equity
    return {
        "final": x,
        "slots": {"debt_after_borrowing_checkpoint": after_borrow},
        "info": {"debt_final": debt_final, "ceiling": ceiling},
    }

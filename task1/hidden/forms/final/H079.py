"""H079 (decimal, usd_million): minimum reported EBITDA for a target equity value.

The reading, in the stated order:
* Net debt = total debt - cash (the only EV-to-equity adjustments).  Signed:
  cash above debt gives negative net debt, which lowers EV.
* Enterprise value = target equity value + net debt.
* Required normalized EBITDA = EV / multiple ("values normalized EBITDA at m").
* Restore the deduction: reported EBITDA = normalized + recurring deduction.
Slot net_debt_checkpoint = debt - cash.
"""
from hlib import num

KEY = "H079"


def solve(b):
    equity = num(b, "a target equity value of {N}.")
    debt, cash = num(b, "total debt of {N} and cash of {N},")
    mult = num(b, "values normalized EBITDA at {N}.")
    ded = num(b, "a recurring EBITDA deduction of {N} from the reported figure.")
    net_debt = debt - cash
    ev = equity + net_debt
    normalized = ev / mult
    return {
        "final": normalized + ded,
        "slots": {"net_debt_checkpoint": net_debt},
        "info": {"ev": ev, "normalized_ebitda": normalized},
    }

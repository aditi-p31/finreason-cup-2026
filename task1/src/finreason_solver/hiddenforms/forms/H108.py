"""H108 (decimal, usd): maximum additional gross income within a tax budget.

The reading:
* Remaining budget = total budget - committed.
* Additional tax on extra gross income G = rate x inclusion x G ("Additional
  taxable income is charged at r, and only f of additional gross income enters
  the taxable base").
* "stays within the tax budget": committed + rate x inclusion x G <= total
  budget, so the exact maximum is G = (total - committed) / (rate x inclusion).
Slot committed_tax_budget_share_checkpoint = committed / total (ratio).
"""
from hlib import num

KEY = "H108"


def solve(b):
    total, committed = num(b, "a taxpayer's total tax budget is {N}, of which {N} is already committed.")
    rate, incl = num(b, "Additional taxable income is charged at {N}, and only {N} of additional gross income enters the taxable base.")
    g = (total - committed) / (rate * incl)
    return {"final": g,
            "slots": {"committed_tax_budget_share_checkpoint": committed / total},
            "info": {"budget_check": committed + rate * incl * g - total}}

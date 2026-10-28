"""H061 (decimal, usd_million): revenue required for a target after-tax income.

The reading, clause by clause:
* Income statement: revenue R, COGS = v * R (variable COGS rate), fixed
  operating costs FC, interest I, tax at rate t on pre-tax income.
* After-tax income = (R * (1 - v) - FC - I) * (1 - t) = NI target.
* R = (NI / (1 - t) + FC + I) / (1 - v).
* Amounts are already in USD millions; no rescaling.
Slot: "after-tax retention ratio" = 1 - t (the share of pre-tax income kept
after tax), unit ratio.
"""
from hlib import num

KEY = "H061"


def solve(b):
    v, fc, i, t = num(b, "a variable COGS rate ratio of {N}, fixed operating costs of {N}, interest expense of {N}, "
                         "and an income tax rate ratio of {N}.")
    ni = num(b, "achieve after-tax income of {N}.")
    keep = 1 - t
    pretax = ni / keep
    revenue = (pretax + fc + i) / (1 - v)
    return {
        "final": revenue,
        "slots": {"retention_ratio_checkpoint": keep},
        "info": {"pretax_income": pretax, "contribution_needed": pretax + fc + i},
    }

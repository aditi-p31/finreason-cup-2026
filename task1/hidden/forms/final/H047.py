"""H047 (decimal, usd): standard versus itemized tax liability.

The reading, clause by clause:
* Gross income G, tax rate t.
* Standard method: deduction D_s, credit C_s.  Itemized method: deduction
  D_i, credit C_i, "may be used only when <flag> is true": eligible = flag.
* Taxable income under a method = G - D (the text states no floor on taxable
  income; every draw has G well above both deductions).
* "Compute both nonnegative net liabilities": liability = max((G - D) * t - C, 0).
* "use the itemized method only when eligible and strictly lower; otherwise
  use the standard method": itemized iff eligible and L_i < L_s (strict), so a
  tie goes to standard.
* Final: the selected liability in USD.
Slots: standard_taxable_checkpoint = G - D_s; itemized_taxable_checkpoint =
G - D_i (both computed regardless of eligibility, as each slot names its
method's taxable income).
"""
from hlib import num, flag, pos

KEY = "H047"


def solve(b):
    gross, rate = num(b, "gross income is {N} and the tax rate is {N}.")
    ds, cs = num(b, "The standard method permits a deduction of {N} and a credit of {N}.")
    di, ci = num(b, "The itemized method permits a deduction of {N} and a credit of {N},")
    elig = flag(b, "it may be used only when {B} is true")
    tax_s = gross - ds
    tax_i = gross - di
    liab_s = pos(tax_s * rate - cs)
    liab_i = pos(tax_i * rate - ci)
    use_i = elig and liab_i < liab_s
    return {
        "final": liab_i if use_i else liab_s,
        "slots": {"standard_taxable_checkpoint": tax_s,
                  "itemized_taxable_checkpoint": tax_i},
        "info": {"eligible": elig, "liability_standard": liab_s,
                 "liability_itemized": liab_i, "itemized_selected": use_i},
    }

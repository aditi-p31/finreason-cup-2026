"""H106 (decimal, percent): action-order effect on normalized asset turnover.

The reading:
* R = retained base after the reduction, D = reduction, so the pre-action base
  P = R + D.  A = the modernization's net capitalized addition.
* Sales factors: modernization (1 + m), reduction (1 - r); each starts at its
  action date and persists, and they compound, so after both actions the
  common period-two factor is (1 + m)(1 - r).  Baseline sales S0 cancel.
* Capex-first: period-one assets P + A, sales (1 + m) S0; period-two assets
  R + A, sales (1 + m)(1 - r) S0.
* Reduction-first: period-one assets R, sales (1 - r) S0; period-two assets
  R + A, sales (1 + m)(1 - r) S0.
* Turnover of an order = (sales1 + sales2) / (assets1 + assets2) (mean over
  mean equals sum over sum).  Normalize by the pre-action turnover S0 / P.
* Answer = (reduction-first factor - capex-first factor) x 100 (percent of
  baseline turnover), signed.
Slots: combined_sales_effect_checkpoint = (1 + m)(1 - r);
shared_second_period_asset_base_checkpoint = R + A.
The body text reads "after a true reduction of"; the form requires the literal
"true" there, since no draw states otherwise.
"""
from hlib import num

KEY = "H106"


def solve(b):
    ret, red = num(b, "{N} is the net total-asset base that remains after a true reduction of {N},")
    add = num(b, "and {N} is the modernization program's net capitalized addition to total assets.")
    m = num(b, "Modernization raises run-rate net sales by {N},")
    r = num(b, "the reduction lowers run-rate net sales by {N};")
    pre = ret + red
    f_mod = 1 + m
    f_red = 1 - r
    f_both = f_mod * f_red
    base2 = ret + add
    capex_first = (f_mod + f_both) / ((pre + add) + base2) * pre
    reduction_first = (f_red + f_both) / (ret + base2) * pre
    return {"final": (reduction_first - capex_first) * 100,
            "slots": {"combined_sales_effect_checkpoint": f_both,
                      "shared_second_period_asset_base_checkpoint": base2},
            "info": {"capex_first_factor": capex_first, "reduction_first_factor": reduction_first,
                     "pre_action_base": pre}}

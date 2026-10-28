"""H044 (decimal, usd): NPV(deferred cleanup plan) - NPV(early cleanup plan).

The reading:
  cleanup cost paid at year T = base * (1 + g)^T (effective annual escalation).
  early plan: outflow base*(1+g)^T1 at end of year T1.
  deferred plan: outflow base*(1+g)^T2 plus fixed admin outflow A, both at end of T2.
  discount at effective annual r, compounded annually: PV = CF / (1 + r)^T.
  Non-cleanup flows cancel, so NPV(plan) = -PV(its cleanup-related outflows), and
  NPV(deferred) - NPV(early) = PV(early outflow) - PV(deferred outflows).
  Sign convention matches "positive favors deferral".
Slots:
  early_cleanup_growth_factor_checkpoint = (1 + g)^T1 (cumulative escalation factor
      to the early payment date).
  terminal_discount_factor_checkpoint = 1 / (1 + r)^T2, read as the standard
      discount factor (present value of 1 paid at the deferred terminal date).
"""
from hlib import num, ipow

KEY = "H044"


def solve(b):
    base = num(b, "The valuation-date base cleanup estimate is {N}.")
    g, t1 = num(b, "nominal effective annual escalation rate {N}, so the early plan pays the resulting cleanup cost at the end of year {N}.")
    t2, admin = num(b, "The deferred plan pays the resulting cleanup cost at the end of year {N}, together with a separate fixed nominal administration outflow of {N} paid only at that terminal date")
    r = num(b, "Discount all cleanup-related cash flows at the nominal effective annual rate {N}, compounded annually")
    grow1 = ipow(1 + g, t1)
    grow2 = ipow(1 + g, t2)
    df1 = 1 / ipow(1 + r, t1)
    df2 = 1 / ipow(1 + r, t2)
    pv_early = base * grow1 * df1
    pv_deferred = (base * grow2 + admin) * df2
    diff = (-pv_deferred) - (-pv_early)
    return {"final": diff,
            "slots": {"early_cleanup_growth_factor_checkpoint": grow1,
                      "terminal_discount_factor_checkpoint": df2},
            "info": {"pv_early_outflow": pv_early, "pv_deferred_outflows": pv_deferred,
                     "t1": t1, "t2": t2, "compound_to_t2": ipow(1 + r, t2)}}

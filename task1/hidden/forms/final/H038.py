"""H038 (decimal, usd): signed terminal-wealth advantage of tax-loss harvesting.

The reading, clause by clause:
* "fully usable eligible loss magnitude of L USD" and "current-year tax rate is
  tau, so the immediate tax reduction is available at time 0": T = L * tau.
  This is the slot immediate_tax_reduction_checkpoint.
* Harvest path: "invests the original P USD principal plus that tax reduction"
  at "the intended rate g minus the additive annual tracking shortfall s", so
  the annual rate is g - s: W_h = (P + T) * (1 + g - s)^N.
* No-harvest path: "the same original principal remains in the intended
  exposure and no tax reduction is received": W_0 = P * (1 + g)^N.
* "Both paths compound annually for N years": integer exponent N.
* "signed terminal wealth advantage of the tax-harvest path over the no-harvest
  path": final = W_h - W_0, negative allowed ("signed").
"""
from hlib import num, ipow

KEY = "H038"


def solve(b):
    loss = num(b, "eligible loss magnitude of {N} USD")
    tau = num(b, "current-year tax rate is {N}, so")
    principal = num(b, "invests the original {N} USD principal")
    g, s = num(b, "equal to the intended rate {N} minus the additive annual tracking shortfall {N}")
    years = num(b, "compound annually for {N} years")
    tax_red = loss * tau
    w_h = (principal + tax_red) * ipow(1 + g - s, years)
    w_0 = principal * ipow(1 + g, years)
    return {"final": w_h - w_0,
            "slots": {"immediate_tax_reduction_checkpoint": tax_red},
            "info": {"harvest_terminal": w_h, "no_harvest_terminal": w_0}}

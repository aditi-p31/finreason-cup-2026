"""H028 (decimal, percent): run-rate EPS accretion/dilution after an acquisition.

The reading:
  predeal share base N0 = E / P (E = aggregate reference equity value, P the
      fixed contractual price; P cancels).
  upfront cash leg = base consideration * cash fraction; stock leg = base - cash.
  earnout settled fully in shares at the same price, incremental to the base.
  new deal shares / N0 = (stock leg + earnout) / E   -> slot deal_share_issuance_checkpoint
  pre-tax interest = cash leg * interest rate (entire cash leg debt-funded)
                                                      -> slot pretax_interest_checkpoint
  pro forma NI = NI_acquirer + NI_target + synergies*(1-t) - interest*(1-t)
      (after-tax synergy and interest each = pre-tax * (1 - t); full shield usable)
  EPS ratio = [NI_pf / (N0 * (1 + s))] / [NI_acquirer / N0] = NI_pf / (NI_acq * (1 + s))
  answer = (EPS ratio - 1) * 100, signed, percent.
"""
from hlib import num

KEY = "H028"


def solve(b):
    equity = num(b, "aggregate reference equity value {N} at one fixed contractual share price")
    base, cash_frac = num(b, "Upfront base consideration is {N}, excluding the earnout; {N} is paid in cash and the remainder in common shares")
    earnout = num(b, "earnout with settlement value {N}, incremental to the base consideration")
    rate = num(b, "debt-funded at annual pre-tax interest rate {N}.")
    ni_a, ni_t = num(b, "standalone after-tax net income is {N} for the acquirer and {N} for the target")
    syn = num(b, "recurring annual pre-tax synergies of {N}.")
    tax = num(b, "With tax rate {N}, after-tax synergies and interest")
    cash_leg = base * cash_frac
    stock_leg = base - cash_leg
    share_ratio = (stock_leg + earnout) / equity
    interest = cash_leg * rate
    ni_pf = ni_a + ni_t + syn * (1 - tax) - interest * (1 - tax)
    eps_ratio = ni_pf / (ni_a * (1 + share_ratio))
    return {"final": (eps_ratio - 1) * 100,
            "slots": {"deal_share_issuance_checkpoint": share_ratio,
                      "pretax_interest_checkpoint": interest},
            "info": {"cash_leg": cash_leg, "stock_leg": stock_leg,
                     "pro_forma_ni": ni_pf, "eps_ratio": eps_ratio}}

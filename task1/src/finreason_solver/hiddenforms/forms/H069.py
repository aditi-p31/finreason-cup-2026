"""H069 (enum): earlier or later retirement date under a required cushion.

The reading, clause by clause:
* Combined principal = savings + one-time contribution today.
* It "earns r annually": annual compounding, projected capital at n years =
  principal * (1 + r)^n.  The slots name this "compound growth factor".
* The "earlier" and "later" dates are identified by their stated labels, with
  their own stated years (draw 2 states the "earlier" date at 6 years and the
  "later" one at 1 year; the labels, not the year counts, name the options).
* Feasible "only if projected capital exceeds its date-specific requirement by
  at least" M: projected - requirement >= M (inclusive, "at least").
* "Prefer the earlier date whenever it is feasible; otherwise choose the later
  date if feasible" -> earlier_date, else later_date, else neither_date.
Slots: earlier / later growth factor = (1 + r)^n for that date's years.
"""
from hlib import num, ipow, first_true

KEY = "H069"


def solve(b):
    saved, contrib = num(b, "A saver has {N} and can add a one-time contribution of {N} today.")
    r = num(b, "The combined amount earns {N} annually")
    n_e, req_e = num(b, "An earlier retirement in {N} years requires capital of {N},")
    n_l, req_l = num(b, "a later retirement in {N} years requires {N}.")
    cushion = num(b, "exceeds its date-specific requirement by at least {N}.")
    principal = saved + contrib
    g_e = ipow(1 + r, n_e)
    g_l = ipow(1 + r, n_l)
    cap_e = principal * g_e
    cap_l = principal * g_l
    ok_e = cap_e - req_e >= cushion
    ok_l = cap_l - req_l >= cushion
    label = first_true([(ok_e, "earlier_date"), (ok_l, "later_date")], otherwise="neither_date")
    return {
        "final": label,
        "slots": {"earlier_growth_factor_checkpoint": g_e, "later_growth_factor_checkpoint": g_l},
        "info": {"capital_earlier": cap_e, "capital_later": cap_l,
                 "surplus_earlier": cap_e - req_e, "surplus_later": cap_l - req_l,
                 "cushion": cushion, "ok_earlier": ok_e, "ok_later": ok_l},
    }

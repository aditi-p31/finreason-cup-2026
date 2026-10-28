"""H111 (decimal, usd_million): reconciled equity value from two valuation methods.

Reading:
* EV_rev = revenue * revenue multiple; EV_ebitda = EBITDA * EBITDA multiple.
* dispersion = higher - lower; permitted = lower * tolerance.
* "consistent within that tolerance": dispersion <= permitted ("within" is
  inclusive per the README table) -> use the mean (EV_rev + EV_ebitda) / 2;
  otherwise use the lower EV.
* equity = chosen EV - total debt + cash (the only adjustments).
* Slots: revenue_value_checkpoint = EV_rev; ebitda_value_checkpoint = EV_ebitda.
Amounts are already in USD millions; no rescaling.
"""
from hlib import num

KEY = "H111"


def solve(b):
    rev, rev_mult = num(b, "The revenue method uses revenue {N} and revenue multiple {N}.")
    ebitda, ebitda_mult = num(b, "The EBITDA method uses EBITDA {N} and EBITDA multiple {N}.")
    tol = num(b, "the permitted dispersion equals the lower value multiplied by {N}.")
    debt, cash = num(b, "Then deduct total debt {N} and add cash {N}, which")
    ev_r = rev * rev_mult
    ev_e = ebitda * ebitda_mult
    hi, lo = max(ev_r, ev_e), min(ev_r, ev_e)
    disp = hi - lo
    permitted = lo * tol
    consistent = disp <= permitted
    ev = (ev_r + ev_e) / 2 if consistent else lo
    return {"final": ev - debt + cash,
            "slots": {"revenue_value_checkpoint": ev_r,
                      "ebitda_value_checkpoint": ev_e},
            "info": {"dispersion": disp, "permitted": permitted,
                     "consistent": consistent, "chosen_ev": ev}}

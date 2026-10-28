"""H086 (enum): expansion / defensive / wait decision.

The reading:
  post-downturn revenue = R * (1 - d)                      -> slot post_downturn_checkpoint
  inflated cost = C * (1 + i)
  expansion surplus = R * (1 - d) * (1 + c) - inflated cost - outlay
      ("applies both downturn and recovery" in sequence, then subtracts cost and outlay)
  defensive surplus = R * (1 - d) - inflated cost
  surplus threshold: "requires ... surplus of at least T" -> surplus >= T (inclusive).
  cash requirement: available cash must cover the one-period outlay -> cash >= outlay
      (inclusive: exactly enough cash funds the outlay).
  Decision list in stated order: expansion if expansion surplus passes AND cash
  passes; otherwise defensive if defensive surplus passes; otherwise wait.
"""
from hlib import num, first_true

KEY = "H086"


def solve(b):
    rev, d, c, outlay = num(b, "starts with revenue {N}, faces downturn ratio {N}, and forecasts recovery ratio {N} if it makes one-period cash outlay {N}.")
    cost, infl = num(b, "Baseline operating cost {N} rises by cost-inflation ratio {N}.")
    cash, thr = num(b, "available cash {N} and requires one-period scenario surplus of at least {N}.")
    post = rev * (1 - d)
    cost_inf = cost * (1 + infl)
    exp_s = post * (1 + c) - cost_inf - outlay
    def_s = post - cost_inf
    exp_ok = exp_s >= thr
    cash_ok = cash >= outlay
    def_ok = def_s >= thr
    label = first_true([(exp_ok and cash_ok, "expansion"), (def_ok, "defensive")],
                       otherwise="wait")
    return {"final": label,
            "slots": {"post_downturn_checkpoint": post},
            "info": {"expansion_surplus": exp_s, "defensive_surplus": def_s,
                     "threshold": thr, "cash": cash, "outlay": outlay,
                     "exp_ok": exp_ok, "cash_ok": cash_ok, "def_ok": def_ok}}

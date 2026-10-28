"""H027 (enum): target-payout vs three-period stable-growth dividend policy.

Reading, clause by clause:
* distributable D = forecast net income - mandatory reserve.
* target-payout dividend T = D * payout; its retained distributable earnings
  D - T must be "at least" floor_T (>=).
* stable-growth dividend S = prior dividend * (1 + g)^3 (exactly three
  periods, stated formula); its retained D - S must be "at least" floor_S (>=).
* a policy qualifies only if its proposed dividend "does not exceed" cap (<=)
  AND its own retained-earnings floor is met.
* both qualify: `target_payout` when T >= S ("at least ... including an exact
  tie"), else `stable_growth`.  Only one: return it.  Neither:
  `no_feasible_policy`.
* Slot one_period_growth_multiple_checkpoint: the one-period growth multiple
  used by the stable policy = 1 + g.
All amounts in USD millions; no unit conversion needed.
"""
from hlib import num, pick_two, ipow

KEY = "H027"


def solve(b):
    ni, reserve = num(b, "forecast net income is {N} and the mandatory reserve is {N}, so")
    payout, floor_t = num(b, "distributable earnings times {N} and requires retained distributable earnings of at least {N}.")
    prior = num(b, "starts from prior total cash dividend {N} at the beginning")
    g = num(b, "at the per-period rate {N}, so")
    floor_s = num(b, "; it requires retained distributable earnings of at least {N}.")
    cap = num(b, "its proposed dividend does not exceed {N} and")
    d = ni - reserve
    t_div = d * payout
    mult = 1 + g
    s_div = prior * ipow(mult, 3)
    ok_t = (t_div <= cap) and (d - t_div >= floor_t)
    ok_s = (s_div <= cap) and (d - s_div >= floor_s)
    label = pick_two(ok_t, ok_s, t_div, s_div, a="target_payout", b="stable_growth",
                     neither="no_feasible_policy", better="higher", tie="target_payout")
    return {"final": label,
            "slots": {"one_period_growth_multiple_checkpoint": mult},
            "info": {"distributable": d, "target_div": t_div, "stable_div": s_div,
                     "cap": cap, "target_retained_minus_floor": d - t_div - floor_t,
                     "stable_retained_minus_floor": d - s_div - floor_s,
                     "cap_minus_target": cap - t_div, "cap_minus_stable": cap - s_div,
                     "ok_target": ok_t, "ok_stable": ok_s}}

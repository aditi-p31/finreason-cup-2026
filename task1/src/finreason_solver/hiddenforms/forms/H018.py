"""H018 (enum): three-stage issuance EPS option choice.

The reading:
* Pro forma earnings per current share for an option = current EPS + the
  earnings the option adds per current share ("adds total earnings of X per
  current share").
* Cumulative share multiple = (1 + per-stage increase)^3 (stated explicitly).
* Pro forma EPS = pro forma earnings per current share / cumulative multiple.
* Qualifies iff pro forma EPS >= floor ("requires pro forma EPS of at least",
  "meets the floor": inclusive).
* Among qualifiers take the higher exact EPS; option_a on an exact tie; the
  sole qualifier if only one; neither_option if none.
Slot a_one_stage_share_multiple_checkpoint = 1 + Option A per-stage increase
(the share-base multiple after one stage).
"""
from hlib import num, ipow, pick_two

KEY = "H018"


def solve(b):
    eps0 = num(b, "current common EPS {N} and")
    floor = num(b, "requires pro forma EPS of at least {N}.")
    add_a, inc_a = num(b, "Option A adds total earnings of {N} per current share, and its per-stage share-base increase is {N};")
    add_b, inc_b = num(b, "Option B analogously adds {N} per current share and uses per-stage increase {N} for")
    m_a = ipow(1 + inc_a, 3)
    m_b = ipow(1 + inc_b, 3)
    eps_a = (eps0 + add_a) / m_a
    eps_b = (eps0 + add_b) / m_b
    label = pick_two(eps_a >= floor, eps_b >= floor, eps_a, eps_b,
                     a="option_a", b="option_b", neither="neither_option",
                     better="higher", tie="option_a")
    return {"final": label,
            "slots": {"a_one_stage_share_multiple_checkpoint": 1 + inc_a},
            "info": {"eps_a": eps_a, "eps_b": eps_b, "floor": floor,
                     "margin_a": eps_a - floor, "margin_b": eps_b - floor}}

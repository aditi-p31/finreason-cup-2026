"""H097 (enum): compliance remediation plan.

The reading:
  capital gap = required capital - current capital
  liquidity gap = required liquidity - liquid assets
  full plan cost = capital gap * capital cost ratio + liquidity gap * liquidity
                   cost ratio + filing cost ("every submitted plan also costs")
  "affordable" = cost <= budget (a cost equal to the budget can be paid; the
  phrase is not in the README table, decided from the sentence).
  1. full_remediation if the full plan is affordable.
  2. Otherwise the single-gap plan for the larger gap: capital_priority when the
     capital gap >= liquidity gap ("capital_priority on an exact gap tie"),
     liquidity_priority when the liquidity gap is larger.  Its cost = that gap *
     its cost ratio + filing cost.  Return the token if affordable, else
     no_feasible_plan.
  Gaps are used exactly as required - current, as the question defines no floor.
  In a draw where current capital exceeds the requirement the capital gap is
  negative; a floor at zero gives the same label there (recorded in info).
Slot capital_coverage_checkpoint ("share of required capital already covered",
ratio) = current capital / required capital.
"""
from hlib import num

KEY = "H097"


def solve(b):
    cap, req_cap = num(b, "an institution has current capital {N} against required capital {N},")
    liq, req_liq = num(b, "and liquid assets {N} against required liquidity {N}.")
    rc = num(b, "Closing one dollar of capital gap costs ratio {N},")
    rl = num(b, "closing one dollar of liquidity gap costs ratio {N},")
    filing = num(b, "every submitted plan also costs {N},")
    budget = num(b, "the total budget is {N}.")
    gc = req_cap - cap
    gl = req_liq - liq
    full_cost = gc * rc + gl * rl + filing
    if full_cost <= budget:
        label = "full_remediation"
        single_cost = None
    else:
        if gc >= gl:
            token, single_cost = "capital_priority", gc * rc + filing
        else:
            token, single_cost = "liquidity_priority", gl * rl + filing
        label = token if single_cost <= budget else "no_feasible_plan"
    floored_full = max(gc, 0) * rc + max(gl, 0) * rl + filing
    return {"final": label,
            "slots": {"capital_coverage_checkpoint": cap / req_cap},
            "info": {"capital_gap": gc, "liquidity_gap": gl, "full_cost": full_cost,
                     "single_cost": single_cost, "budget": budget,
                     "full_cost_with_gaps_floored_at_zero": floored_full}}

"""H064 (enum): green-bond structure choice.

The reading, per structure s in {A, B}:
* compound the principal over the term: principal * (1 + y_s) ** term_s
* interest cost = compounded - principal
* total financing cost = interest cost + issuance cost_s
* feasible iff total cost "does not exceed" cap (<=) AND eligible share
  "reaches" 0.6 (>=), per the README comparison table.
Decision: both feasible -> lower total cost, "prefer structure_a on a cost
tie"; exactly one feasible -> that one; neither -> no_feasible_structure.
Slot structure_a_annual_factor_checkpoint = 1 + y_A, the one-period gross
compound factor for A (unit multiple).
Terms are integers in the text; ipow fails loudly otherwise.
"""
from hlib import num, ipow, pick_two

KEY = "H064"


def solve(b):
    principal = num(b, "for the same principal {N}.")
    ya, ta, ca, sa = num(b, "Structure A has annual yield ratio {N}, term {N}, issuance cost {N}, and eligible-proceeds share {N}.")
    yb, tb, cb, sb = num(b, "Structure B has annual yield ratio {N}, term {N}, issuance cost {N}, and eligible-proceeds share {N}.")
    cap = num(b, "total financing cost does not exceed {N} and")
    share_min = num(b, "its eligible share reaches {N}.")
    fa = 1 + ya
    fb = 1 + yb
    cost_a = principal * ipow(fa, ta) - principal + ca
    cost_b = principal * ipow(fb, tb) - principal + cb
    ok_a = cost_a <= cap and sa >= share_min
    ok_b = cost_b <= cap and sb >= share_min
    label = pick_two(ok_a, ok_b, cost_a, cost_b, a="structure_a", b="structure_b",
                     neither="no_feasible_structure", better="lower", tie="structure_a")
    return {
        "final": label,
        "slots": {"structure_a_annual_factor_checkpoint": fa},
        "info": {"cost_a": cost_a, "cost_b": cost_b, "cap": cap,
                 "cap_minus_cost_a": cap - cost_a, "cap_minus_cost_b": cap - cost_b,
                 "share_a": sa, "share_b": sb, "share_min": share_min,
                 "ok_a": ok_a, "ok_b": ok_b},
    }

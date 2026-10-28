"""H063 (enum): household budget-cut response.

The reading, clause by clause:
* Total budget B; "A cut of c is imposed": c is a fraction of the budget (the
  budgets are in the hundreds or thousands and c is 0.2 or 0.25), so the
  post-cut budget is B * (1 - c).  Slot post_cut_budget_checkpoint.
* "protected spending of S_p and planned flexible spending of S_f are intended
  to continue": the funding gap = S_p + S_f - B * (1 - c).
* "Flexible spending may not fall below F": the flexible spending available for
  reduction = S_f - F.  Slot reducible_spending_checkpoint.
* "at most E of outside funding is available": outside capacity E.
* Decision list in stated precedence: "Prefer reducing flexible spending if
  that alone covers the funding gap" -> reduce_flexible_spending when
  S_f - F >= gap; "otherwise use outside funding if it alone covers the gap"
  -> use_external_funding when E >= gap; else no_feasible_response.
  "covers" is read as inclusive (>=): an amount equal to the gap closes it.
"""
from hlib import num, first_true

KEY = "H063"


def solve(b):
    budget = num(b, "starts with a total budget of {N}.")
    cut = num(b, "A cut of {N} is imposed")
    prot, flex = num(b, "protected spending of {N} and planned flexible spending of {N} are intended")
    floor_, ext = num(b, "Flexible spending may not fall below {N}, and at most {N} of outside funding")
    post = budget * (1 - cut)
    gap = prot + flex - post
    reducible = flex - floor_
    label = first_true([(reducible >= gap, "reduce_flexible_spending"),
                        (ext >= gap, "use_external_funding")],
                       otherwise="no_feasible_response")
    return {"final": label,
            "slots": {"post_cut_budget_checkpoint": post,
                      "reducible_spending_checkpoint": reducible},
            "info": {"gap": gap, "reducible_minus_gap": reducible - gap,
                     "external_minus_gap": ext - gap}}

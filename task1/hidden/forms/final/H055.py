"""H055 (enum): capped linear-plus-convexity loss against a budget.

The reading:
* linear loss rate = linear sensitivity * shock.
* convexity loss rate = convexity multiplier * shock^2 ("applies to the
  square of the shock").
* gross dollar loss = portfolio value * (linear rate + convexity rate).
* capped loss = min(gross loss, cap).
* "within_budget when the capped loss does not exceed the budget" ->
  capped <= budget (inclusive, "does not exceed"); budget_breach otherwise.
Slot: convexity loss ratio = convexity multiplier * shock^2.

Note: reading the linear rate as the bare sensitivity (not times the shock)
gives the same labels on all three draws, because the cap binds either way;
the slot does not depend on that choice.
"""
from hlib import num

KEY = "H055"


def solve(b):
    value, shock = num(b, "A portfolio worth {N} faces positive downside shock ratio {N}.")
    lin = num(b, "Its linear loss sensitivity is {N}, and")
    cvx = num(b, "its convexity multiplier {N} applies to the square of the shock")
    cap = num(b, "cap that loss at {N}.")
    budget = num(b, "Compare the capped loss with budget {N}.")

    lin_rate = lin * shock
    cvx_rate = cvx * shock * shock
    gross = value * (lin_rate + cvx_rate)
    capped = min(gross, cap)
    label = "within_budget" if capped <= budget else "budget_breach"
    return {
        "final": label,
        "slots": {"convexity_ratio_checkpoint": cvx_rate},
        "info": {"gross_loss": gross, "capped_loss": capped,
                 "budget_minus_capped": budget - capped},
    }

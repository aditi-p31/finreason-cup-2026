"""H110 (enum): social-impact program choice with three delivery opportunities.

The reading, clause by clause:
* per program: total cost = fixed cost + per-unit delivery cost * volume.
* three independent opportunities with the same per-opportunity success
  probability p; value is realized once if at least one succeeds, so
  effective probability = 1 - (1 - p)^3.
* planned monetized social value = value per unit * volume.
  expected net social value = planned value * effective probability - total cost.
* feasible only when total cost does not exceed the budget (cost <= budget,
  "does not exceed") and volume reaches the minimum (volume >= minimum,
  "reaches").
* Choose the feasible program with the higher expected net social value,
  program_a on an exact tie, the sole feasible one, else no_feasible_program.

Slot program_a_failure_probability_checkpoint "failure probability for one
program A delivery opportunity" = 1 - p_A (one opportunity, not all three).
"""
from hlib import num, ipow, pick_two

KEY = "H110"


def solve(b):
    fa, ua, va, sa, pa = num(
        b, "Compare social-impact program A, with fixed cost {N}, aggregate delivery cost per "
           "beneficiary-equivalent unit {N}, beneficiary-equivalent volume {N}, monetized social "
           "value per unit {N}, and per-opportunity success probability {N}, against program B")
    fb, ub, vb, sb, pb = num(b, "against program B with corresponding inputs {N}, {N}, {N}, {N}, and {N}.")
    budget, min_vol = num(b, "feasible only when total cost does not exceed {N} and its volume reaches {N}.")

    def evaluate(fixed, unit, vol, sv, p):
        cost = fixed + unit * vol
        eff = 1 - ipow(1 - p, 3)
        ensv = sv * vol * eff - cost
        ok = (cost <= budget) and (vol >= min_vol)
        return cost, eff, ensv, ok

    ca, ea, na, oka = evaluate(fa, ua, va, sa, pa)
    cb, eb, nb, okb = evaluate(fb, ub, vb, sb, pb)
    label = pick_two(oka, okb, na, nb, a="program_a", b="program_b",
                     neither="no_feasible_program", better="higher", tie="program_a")
    return {
        "final": label,
        "slots": {"program_a_failure_probability_checkpoint": 1 - pa},
        "info": {"cost_a": ca, "cost_b": cb, "ensv_a": na, "ensv_b": nb,
                 "feasible_a": oka, "feasible_b": okb, "budget": budget, "min_vol": min_vol},
    }

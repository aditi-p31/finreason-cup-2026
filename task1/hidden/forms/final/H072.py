"""H072 (enum): residual-value revision scenarios over three subperiods.

The reading, clause by clause:
* net book value NBV = original cost - accumulated depreciation.
* per scenario: depreciable balance above residual D0 = NBV - residual; in each
  of three sequential subperiods depreciation = ratio x (balance above residual),
  so the balance above residual after three stages is D0 x (1 - ratio)^3 and the
  cumulative three-stage depreciation is D0 - D0 x (1 - ratio)^3.
* qualifies iff cumulative <= cap ("at most", inclusive) AND remaining balance
  above residual >= floor ("at least", inclusive).
* among qualifiers pick the LOWER cumulative depreciation; exact tie -> Scenario A;
  sole qualifier wins; none -> Neither scenario.
Slot a_one_stage_retention_factor_checkpoint = 1 - Scenario A's ratio (the share of
the balance above residual retained after one subperiod).
"""
from hlib import num, pick_two, ipow

KEY = "H072"


def solve(b):
    cost, accum = num(b, "An asset has original cost {N} and accumulated depreciation of {N} in")
    ra, da = num(b, "Scenario A revises residual value to {N} and applies per-subperiod depreciation ratio {N};")
    rb, db = num(b, "Scenario B uses {N} and {N}.")
    cap = num(b, "cumulative three-stage depreciation is at most {N} and")
    floor_ = num(b, "remaining depreciable balance above residual is at least {N}.")
    nbv = cost - accum

    def run(res, d):
        d0 = nbv - res
        rem = d0 * ipow(1 - d, 3)
        return d0 - rem, rem

    cum_a, rem_a = run(ra, da)
    cum_b, rem_b = run(rb, db)
    ok_a = cum_a <= cap and rem_a >= floor_
    ok_b = cum_b <= cap and rem_b >= floor_
    label = pick_two(ok_a, ok_b, cum_a, cum_b, a="Scenario A", b="Scenario B",
                     neither="Neither scenario", better="lower", tie="Scenario A")
    return {"final": label,
            "slots": {"a_one_stage_retention_factor_checkpoint": 1 - da},
            "info": {"cum_a": cum_a, "rem_a": rem_a, "cum_b": cum_b, "rem_b": rem_b,
                     "cap": cap, "floor": floor_, "ok_a": ok_a, "ok_b": ok_b}}

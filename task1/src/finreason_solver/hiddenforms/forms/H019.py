"""H019 (decimal, multiple): maximum common stress activity across three constraints.

The reading, clause by clause:
* Starting values (USD millions): eligible capital EC, Tier 1 T1, risk-weighted
  assets RWA, total exposure EXP, HQLA, total net cash outflows NCO.
* Ratios: minimum capital ratio mc, buffer ratio bf, minimum leverage ratio lv,
  minimum liquidity ratio lq.
* Per unit of x: EC falls by a, T1 falls by t, RWA rises by w, exposure rises by
  e, HQLA falls by h, NCO rises by n (all given as "<coef>*x").
* "Add the minimum capital ratio and buffer ratio to obtain k": k = mc + bf.
  Slot combined_capital_requirement_ratio_checkpoint is k (unrounded here;
  run_forms rounds it to 6 dp; "use its exact unrounded value downstream").
* The three capacities are the stated formulas, transcribed literally:
    c1 = (EC - k*RWA) / (a + k*w)
    c2 = (T1 - lv*EXP) / (t + lv*e)
    c3 = (HQLA - lq*NCO) / (h + lq*n)
* "Return the smallest of the three capacities": final = min(c1, c2, c3).
  No clamp at zero is stated.  Each constraint is linear in x with a positive
  denominator, so constraint i holds exactly when x <= c_i, and the largest x
  satisfying all three is min(c_i) even when one c_i is negative (a constraint
  already breached at x = 0).  So the literal min is also the mathematically
  stated "maximum common stress activity allowed by all constraints".

Adjudication (batch 14): readers A and B agree.  On the first draw the
liquidity numerator is already negative, so the "positive x" presupposition
fails for that constraint.  The text states the three formulas verbatim and
no clamp or exclusion, so the literal min is kept.  Alternative readings
(clamp to 0, or drop non-positive capacities) are unstated and not used.
"""
from hlib import num

KEY = "H019"


def solve(b):
    ec, t1, rwa, exp_, hqla, nco = num(
        b, "begins with eligible capital {N}, Tier 1 capital {N}, risk-weighted assets {N}, "
           "total exposure {N}, high-quality liquid assets {N}, and total net cash outflows {N}, "
           "all in USD millions")
    mc, bf, lv, lq = num(
        b, "minimum capital ratio {N}, capital buffer ratio {N}, minimum leverage ratio {N}, "
           "and minimum liquidity ratio {N} as decimal ratios")
    a, t, w, e, h, n = num(
        b, "decreases eligible capital by {N}*x and Tier 1 capital by {N}*x, while increasing "
           "risk-weighted assets by {N}*x, exposure by {N}*x, reducing HQLA by {N}*x, and "
           "increasing net cash outflows by {N}*x")
    k = mc + bf
    c1 = (ec - k * rwa) / (a + k * w)
    c2 = (t1 - lv * exp_) / (t + lv * e)
    c3 = (hqla - lq * nco) / (h + lq * n)
    return {"final": min(c1, c2, c3),
            "slots": {"combined_capital_requirement_ratio_checkpoint": k},
            "info": {"capital_capacity": c1, "leverage_capacity": c2,
                     "liquidity_capacity": c3}}

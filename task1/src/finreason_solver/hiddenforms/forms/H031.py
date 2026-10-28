"""H031 (enum): risk-appetite and liquidity gate on a proposed exposure.

REVISED 2026-10-19 (the author's decision): the proportional haircut,
a * (1 - h), is restored.  On 2026-10-02 the author had switched to
subtraction, a - h (kept as H031.py.subtraction-20261002).  A blind
independent re-solve of all 116 hidden templates on 2026-10-18 read the haircut
proportionally, and a blind three-lens referee panel (literal text, generator
design, finance convention) chose the proportional reading 3 to 0.  Decisive:
the nudged base 0.500001 puts the 6-dp slot at exactly 0.2500005, the planted
half-up tie this generator uses elsewhere (H030, H112); under the proportional
reading the three draws also give all three labels.  The code below is the
reviewed form H031.py.pre-subtraction byte for byte apart from this note.
Earlier history: readers A and B (and the pilot) read subtraction; the batch-7
adjudicator applied the haircut proportionally.

The reading, clause by clause:
* Capital K, base risk-appetite ratio a, downturn haircut h, volatility uplift u.
* "Reduce the base appetite by the downturn haircut": a haircut is a
  proportional reduction, so the haircut-adjusted appetite is a * (1 - h).
  Grounds:
  1. In finance a haircut of h reduces a quantity by the fraction h of itself.
  2. The same question set uses exactly this construction and spells it out:
     "this threshold is reduced by haircut ratio 0.2499995, so the
     single-transfer threshold is the rolling threshold times
     (1-single-threshold haircut ratio)".  "Reduced by haircut ratio" there
     means times (1 - ratio).
  3. The two stress adjustments are then parallel relative adjustments: a
     proportional haircut, then "divide it by one plus the volatility uplift".
  Corroboration only (never used to choose the formula at run time): the one
  nudged input, base 0.500001 against haircut 0.5, puts the 6-dp slot at
  exactly 0.2500005, a half-up boundary.  That is the same construction the
  generator uses for the 6-dp factor slots of H030 (0.7000005) and H112
  (0.1000005).  Under subtraction the nudge produces 0.000001 and serves no
  rounding or decision boundary.
* "divide it by one plus the volatility uplift": stressed ratio
  s = a * (1 - h) / (1 + u).
* "apply the result to capital": stressed risk budget = s * K.
* "available excess liquidity" = max(L, R) - R, with L liquid assets and R the
  reserve that must remain uncommitted.
* "binding exposure limit" = min(stressed budget, excess liquidity).
* Decision list, in stated order:
  1. liquidity_block if the original liquid assets do not cover the reserve:
     "cover" means L >= R, so block when L < R (strict).
  2. within_appetite when proposed exposure E is "within" the binding limit:
     E <= limit (README table: within -> <=).
  3. otherwise reduce_exposure.
Slot stressed_ratio_checkpoint: "appetite ratio after both stress adjustments"
= a * (1 - h) / (1 + u) (ratio).
The subtraction alternative (a - h) / (1 + u) is recorded in info only.
"""
from hlib import num, first_true

KEY = "H031"


def solve(b):
    cap, base, hair, upl = num(b, "A firm has capital {N}, base risk-appetite ratio {N}, a downturn haircut {N}, and a volatility uplift {N}.")
    liq, reserve, expo = num(b, "Its liquid assets are {N}, of which {N} must remain uncommitted, and it proposes exposure {N}.")
    stressed_ratio = base * (1 - hair) / (1 + upl)
    budget = stressed_ratio * cap
    excess = max(liq, reserve) - reserve
    limit = min(budget, excess)
    label = first_true(
        [(liq < reserve, "liquidity_block"),
         (expo <= limit, "within_appetite")],
        otherwise="reduce_exposure",
    )
    alt_ratio = (base - hair) / (1 + upl)
    alt_limit = min(alt_ratio * cap, excess)
    return {
        "final": label,
        "slots": {"stressed_ratio_checkpoint": stressed_ratio},
        "info": {"stressed_budget": budget, "excess_liquidity": excess,
                 "binding_limit": limit, "exposure_minus_limit": expo - limit,
                 "alt_subtraction_ratio": alt_ratio,
                 "alt_subtraction_limit": alt_limit},
    }

"""H058 (decimal, percent): minimum backup-review conditional detection ratio.

Adjudicated (batch 15).  Readers A and B agree on the model and differ only
on whether to floor the result at zero; this form keeps the stated equation
unfloored (reader B's reading).

The reading, clause by clause:
* Primary detects ratio p of the population.  The backup is applied only to
  the missed set (ratio 1 - p) and detects conditional ratio x of it, so the
  stages do not overlap: unique combined detection = p + (1 - p) * x.
  "Do not assume independent detectors or apply inclusion-exclusion" rules
  out p + x - p * x.
* "reaches the target" is >= (README table).  Combined detection increases
  in x, so the minimum x is the solution of the equality:
  x = (T - p) / (1 - p).
* Report as a percentage: x * 100.

Floor at zero: the text gives no floor.  It asserts "the primary ratio
strictly below the target", i.e. it states the equation assuming a
non-negative solution, and it never says what to report when the primary
already meets the target.  Following the project precedent for an unmet
stated premise with no stated floor (H029, H032, H040, H075: report the
equation as solved; H089 floors only because its text says the credit
"cannot be negative"), the equation is reported as solved.  A draw with
p = T gives exactly 0 under either reading; a draw with p > T gives a
negative value here, and the clamped alternative (0) is kept in info.

Slot primary_miss_checkpoint ("complement ratio remaining after primary
review", unit ratio) = 1 - p.
"""
from hlib import num

KEY = "H058"


def solve(b):
    p = num(b, "a primary review detects exact decimal ratio {N} of one fixed eligible transaction population")
    t = num(b, "The target unique combined detection ratio is {N}, with the primary ratio strictly below the target.")
    miss = 1 - p
    x = (t - p) / miss
    return {
        "final": x * 100,
        "slots": {"primary_miss_checkpoint": miss},
        "info": {"primary": p, "target": t, "backup_ratio": x,
                 "clamped_alternative_pct": max(x, 0) * 100,
                 "primary_minus_target": p - t},
    }

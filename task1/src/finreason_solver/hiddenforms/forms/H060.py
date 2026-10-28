"""H060 (enum): review policy from signed risk-score migration and flags.

The reading, clause by clause:
* signed migration m = current risk score - prior risk score.
* Base: "Enhanced review when that signed migration reaches the positive
  material-migration threshold or current risk reaches the elevated-current-
  risk threshold" -> m >= migration threshold OR current >= elevated threshold
  ("reaches" = >=, inclusive; a negative migration can never reach the
  positive threshold); otherwise Routine monitoring.
* Precedence: suspicious activity true is highest -> Restrict and investigate;
  else stale documentation true overrides the base -> Suspend and refresh
  records; else the base label.

Slot risk_migration_checkpoint = m (signed).
"""
from hlib import num, flag, first_true

KEY = "H060"


def solve(b):
    prior, current, mig_thr, elev_thr = num(
        b, "A customer's prior risk score is {N}, current risk score is {N}, "
           "material-migration threshold is {N}, and elevated-current-risk threshold is {N}.")
    susp = flag(b, "reports suspicious activity {B}")
    stale = flag(b, "and stale documentation {B}.")
    mig = current - prior
    base = "Enhanced review" if (mig >= mig_thr or current >= elev_thr) else "Routine monitoring"
    label = first_true([
        (susp, "Restrict and investigate"),
        (stale, "Suspend and refresh records"),
    ], otherwise=base)
    return {
        "final": label,
        "slots": {"risk_migration_checkpoint": mig},
        "info": {"migration": mig, "mig_margin": mig - mig_thr,
                 "current_margin": current - elev_thr, "base": base},
    }

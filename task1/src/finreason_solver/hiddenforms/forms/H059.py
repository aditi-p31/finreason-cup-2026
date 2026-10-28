"""H059 (enum): monitoring action from growth, ratcheted corridor threshold and flags.

The reading, clause by clause:
* "Current-window activity consists of D and N" = daytime and overnight volume
  (the growth-ratio definition names them in that order); H = historical volume.
* growth = (D + N - H) / H; "its strict trigger threshold is g": the growth
  threshold is exceeded when growth > g (strict).
* corridor total C; baseline corridor threshold B; three sequential stages each
  reduce the surviving threshold by fraction s: effective = B * (1 - s)^3.
* "both the growth threshold and effective corridor threshold are strictly
  exceeded": growth > g AND C > effective (strict, as stated).
* "or when either metadata flag is present": rapid-velocity flag OR
  incomplete-originator flag.  The mandatory-hold flag is not a metadata trigger;
  it is used only in the action rule.
* decision list in stated order: Hold if trigger and mandatory-hold; else
  Investigate if trigger; else Routine monitoring.

Slot corridor_threshold_residual_factor_checkpoint: fraction of the threshold
retained after one stage = 1 - s.
"""
from hlib import num, flag, ipow, first_true

KEY = "H059"


def solve(b):
    day, night, hist = num(
        b,
        "Current-window activity consists of {N} and {N}, while comparable historical-window activity was {N}.",
    )
    g_thr = num(b, "its strict trigger threshold is {N}.")
    corridor = num(b, "elevated-risk corridor total {N}.")
    base = num(b, "The baseline corridor threshold is {N}.")
    s = num(b, "reduce the surviving threshold by fraction {N} of its then-current value")
    rapid = flag(b, "a rapid-velocity flag of {B},")
    incomplete = flag(b, "an incomplete-originator flag of {B},")
    hold = flag(b, "a mandatory-hold flag of {B}.")

    growth = (day + night - hist) / hist
    residual = 1 - s
    effective = base * ipow(residual, 3)
    growth_hit = growth > g_thr
    corridor_hit = corridor > effective
    trigger = (growth_hit and corridor_hit) or rapid or incomplete
    label = first_true(
        [(trigger and hold, "Hold"), (trigger, "Investigate")],
        otherwise="Routine monitoring",
    )
    return {
        "final": label,
        "slots": {"corridor_threshold_residual_factor_checkpoint": residual},
        "info": {"growth": growth, "growth_threshold": g_thr, "corridor": corridor,
                 "effective_threshold": effective, "rapid": rapid,
                 "incomplete": incomplete, "hold": hold, "trigger": trigger},
    }

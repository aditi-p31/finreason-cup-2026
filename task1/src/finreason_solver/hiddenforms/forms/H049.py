"""H049 (enum): three-layer tolerance assurance check.

The reading, clause by clause:
* For each metric (energy, waste-management): lower = reported * (1-t)^3,
  upper = reported * (1+t)^3; "the final inclusive envelope" -> the audited
  amount passes when lower <= audited <= upper (both ends inclusive).
* "Audit coverage C must reach M" -> C >= M ("reach" is inclusive per the
  README table).
* The literal true/false before "indicates that the completed engagement
  covered both metrics and issued an unmodified conclusion" must be true.
* "Return assured only when every condition holds; otherwise return
  review_required."
Slot lower_stage_factor_checkpoint: "the one-layer lower tolerance factor" =
1 - t (each layer multiplies the lower bound by 1-t).
"""
from hlib import num, flag, ipow

KEY = "H049"


def solve(b):
    rep_e, aud_e = num(b, "checks reported energy savings {N} against audited energy savings {N}")
    rep_w, aud_w = num(b, "reported waste-management savings {N} against audited waste-management savings {N}")
    t = num(b, "the per-layer tolerance ratio {N} applies")
    cov, cov_min = num(b, "Audit coverage {N} must reach {N}")
    ok_flag = flag(b, "and {B} indicates that the completed engagement")

    lo_f = ipow(1 - t, 3)
    hi_f = ipow(1 + t, 3)
    in_e = rep_e * lo_f <= aud_e <= rep_e * hi_f
    in_w = rep_w * lo_f <= aud_w <= rep_w * hi_f
    cov_ok = cov >= cov_min
    label = "assured" if (in_e and in_w and cov_ok and ok_flag) else "review_required"
    return {"final": label,
            "slots": {"lower_stage_factor_checkpoint": 1 - t},
            "info": {"energy_lo": rep_e * lo_f, "energy_hi": rep_e * hi_f, "energy_in": in_e,
                     "waste_lo": rep_w * lo_f, "waste_hi": rep_w * hi_f, "waste_in": in_w,
                     "coverage_ok": cov_ok, "flag": ok_flag}}

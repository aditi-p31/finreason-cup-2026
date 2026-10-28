"""H007 (enum): bond choice on holding-period return with a duration cap.

The reading, clause by clause:
* total received cash = redemption + aggregate coupons.
* total acquisition outlay = clean price + settlement cost (settlement cost
  already includes accrued interest and fees; nothing is added again).
* HPR = (received - outlay) / outlay.
* Qualifies only if HPR "is at least" the ratio (>=) AND modified duration
  "is at most" the cap (<=).
* Among qualifiers, the higher exact HPR wins; "choose Bond A on an exact tie";
  the sole qualifier wins; "Neither when neither qualifies".
Slots: a_outlay / b_outlay = clean price + settlement cost of each bond (usd).
"""
from hlib import num, pick_two

KEY = "H007"


def _bond(b, name):
    red, cpn, clean, settle, dur = num(
        b, "Bond " + name + " has expected redemption cash {N}, aggregate coupon cash {N}, "
        "clean price {N}, settlement cost {N}, and modified duration {N}.")
    received = red + cpn
    outlay = clean + settle
    hpr = (received - outlay) / outlay
    return outlay, hpr, dur


def solve(b):
    out_a, hpr_a, dur_a = _bond(b, "A")
    out_b, hpr_b, dur_b = _bond(b, "B")
    thr, dcap = num(b, "exact holding-period return is at least the exact ratio {N} and its modified duration is at most {N}.")
    ok_a = hpr_a >= thr and dur_a <= dcap
    ok_b = hpr_b >= thr and dur_b <= dcap
    label = pick_two(ok_a, ok_b, hpr_a, hpr_b, a="Bond A", b="Bond B", neither="Neither",
                     better="higher", tie="Bond A")
    return {
        "final": label,
        "slots": {"a_outlay_checkpoint": out_a, "b_outlay_checkpoint": out_b},
        "info": {"hpr_a": hpr_a, "hpr_b": hpr_b, "threshold": thr, "dur_a": dur_a,
                 "dur_b": dur_b, "dur_cap": dcap, "ok_a": ok_a, "ok_b": ok_b},
    }

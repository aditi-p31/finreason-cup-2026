"""H090 (enum): financing package under a three-stage leverage ceiling ratchet.

Reading:
* opening assets A0, liabilities L0 (USD millions); opening equity = A0 - L0.
* a package adds equity proceeds e and debt proceeds d: post assets
  A0 + e + d, post liabilities L0 + d, post equity (A0 - L0) + e.
* ceiling starts at 1.00 and each of three stages multiplies the remaining
  ceiling by (1 - t): final ceiling = (1 - t)^3 (stated).
* qualifies only if post equity is "at least" floor (>=) AND ratio
  liabilities / assets "does not exceed that final inclusive ceiling" (<=).
* both qualify: lower exact ratio wins, Package A on an exact tie; one
  qualifies: that one; none: `Neither package`.
* Slot one_stage_leverage_cap_checkpoint: the one-stage cap factor = 1 - t.
"""
from hlib import num, pick_two, ipow

KEY = "H090"


def solve(b):
    a0, l0 = num(b, "A company begins with assets of {N} and liabilities of {N} in USD millions.")
    ea, da = num(b, "Financing Package A adds equity proceeds of {N} and debt proceeds of {N}.")
    eb, db = num(b, "Financing Package B adds equity proceeds of {N} and debt proceeds of {N}.")
    t = num(b, "reduces the remaining ceiling by the same fraction {N}, so")
    eq_floor = num(b, "its post-financing equity is at least {N} and")
    step = 1 - t
    ceiling = ipow(step, 3)

    def package(e, d):
        assets = a0 + e + d
        liabs = l0 + d
        equity = assets - liabs
        ratio = liabs / assets
        return ratio, equity, (equity >= eq_floor and ratio <= ceiling)

    ra, eqa, oka = package(ea, da)
    rb, eqb, okb = package(eb, db)
    label = pick_two(oka, okb, ra, rb, a="Package A", b="Package B",
                     neither="Neither package", better="lower", tie="Package A")
    return {"final": label,
            "slots": {"one_stage_leverage_cap_checkpoint": step},
            "info": {"ceiling": ceiling, "ratio_a": ra, "ratio_b": rb,
                     "equity_a": eqa, "equity_b": eqb, "floor": eq_floor,
                     "ceiling_minus_ratio_a": ceiling - ra, "ceiling_minus_ratio_b": ceiling - rb,
                     "ok_a": oka, "ok_b": okb}}

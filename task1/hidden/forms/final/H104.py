"""H104 (enum): choose between two financing scenarios by WACC and debt ratio.

The reading:
* ceiling = 1.00 * (1 - t)^3 ("reduces the remaining ceiling by the same
  fraction t" at each of three stages; the text also writes (1-t)^3).
* WACC (percent) = E/(D+E) * Ke% + D/(D+E) * Kd% * (1 - tax).
* Qualifies when WACC <= maximum permitted WACC percentage and
  D/(D+E) <= permitted ceiling.  "maximum permitted" and "permitted ceiling"
  are limits that the value may equal, so both comparisons are inclusive.
* Among qualifiers the lower exact WACC wins, Scenario A on an exact tie;
  a sole qualifier wins; Neither scenario when none qualifies.
Slot: ceiling remaining after one stage = 1.00 * (1 - t).
"""
from hlib import num, ipow, pick_two, F

KEY = "H104"


def _scenario(b, name):
    e, d, ke, kd = num(
        b,
        "Scenario " + name + " has equity value {N}, debt value {N}, cost of equity percentage {N}, and pre-tax cost of debt percentage {N}.",
    )
    return e, d, ke, kd


def solve(b):
    tax, wmax = num(b, "using corporate tax rate ratio {N} and maximum permitted WACC percentage {N}.")
    start = num(b, "its permitted ceiling starts at {N}.")
    t = num(b, "by the same fraction t={N}, so")

    one_stage = start * (1 - t)
    ceiling = start * ipow(1 - t, 3)

    res = {}
    for name in ("A", "B"):
        e, d, ke, kd = _scenario(b, name)
        v = e + d
        dr = d / v
        wacc = e / v * ke + d / v * kd * (1 - tax)
        res[name] = (wacc, dr, wacc <= wmax and dr <= ceiling)

    label = pick_two(res["A"][2], res["B"][2], res["A"][0], res["B"][0],
                     a="Scenario A", b="Scenario B", neither="Neither scenario",
                     better="lower", tie="Scenario A")
    return {
        "final": label,
        "slots": {"one_stage_debt_ratio_cap_checkpoint": one_stage},
        "info": {
            "ceiling": ceiling,
            "wacc_A": res["A"][0], "dr_A": res["A"][1], "ok_A": res["A"][2],
            "wacc_B": res["B"][0], "dr_B": res["B"][1], "ok_B": res["B"][2],
            "wmax_minus_wacc_A": wmax - res["A"][0],
            "wmax_minus_wacc_B": wmax - res["B"][0],
            "ceiling_minus_dr_A": ceiling - res["A"][1],
            "ceiling_minus_dr_B": ceiling - res["B"][1],
        },
    }

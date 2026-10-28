"""H025 (decimal, usd): minimum gross terminal salvage meeting two NPV floors.

The reading:
* Conditional NPV in a scenario with rate r (no probability inside):
  NPV(S) = -cost + interim / (1 + r)^n1 + (S - cleanup) / (1 + r)^n2,
  where n1 is the interim horizon and n2 the terminal horizon ("pays cleanup
  cost ... together with salvage after n2 whole years"; same gross salvage and
  cleanup in both scenarios).  Rates compound over whole years.
* Stress: probability p, rate r_s.  Normal: probability 1 - p, rate r_n.
* Expected NPV = p x NPV_stress + (1 - p) x NPV_normal.
* Both NPVs rise with S, so each "at least" floor (>=) gives a lower bound on S:
    S_exp    = cleanup + (E_floor + cost - interim x (p d_s1 + (1-p) d_n1)) / (p d_s2 + (1-p) d_n2)
    S_stress = cleanup + (S_floor + cost - interim x d_s1) / d_s2
  with d_x = 1 / (1 + r_x)^n.  The minimum salvage meeting both is max(S_exp, S_stress).
Slots: normal / stressed interim PV = interim / (1 + r)^n1, conditional (not
probability weighted).
"""
from hlib import num, ipow

KEY = "H025"


def solve(b):
    cost = num(b, "A project costs {N} USD now")
    interim, n1 = num(b, "produces an interim cash flow of {N} USD after {N} whole years")
    cleanup, n2 = num(b, "pays cleanup cost {N} USD together with salvage after {N} whole years")
    p, rs = num(b, "The stress scenario has probability {N} and effective annual discount rate {N};")
    rn = num(b, "the normal scenario has probability one minus that probability and effective annual discount rate {N}.")
    e_floor, s_floor = num(b, "makes expected NPV at least {N} USD and stressed-scenario NPV at least {N} USD?")
    pn = 1 - p
    ds1 = 1 / ipow(1 + rs, n1)
    ds2 = 1 / ipow(1 + rs, n2)
    dn1 = 1 / ipow(1 + rn, n1)
    dn2 = 1 / ipow(1 + rn, n2)
    pv_s = interim * ds1
    pv_n = interim * dn1
    s_exp = cleanup + (e_floor + cost - (p * pv_s + pn * pv_n)) / (p * ds2 + pn * dn2)
    s_str = cleanup + (s_floor + cost - pv_s) / ds2
    salvage = max(s_exp, s_str)

    def npv(d1, d2):
        return -cost + interim * d1 + (salvage - cleanup) * d2

    npv_s = npv(ds1, ds2)
    npv_n = npv(dn1, dn2)
    return {"final": salvage,
            "slots": {"normal_interim_present_value_checkpoint": pv_n,
                      "stressed_interim_present_value_checkpoint": pv_s},
            "info": {"salvage_expected_bound": s_exp, "salvage_stress_bound": s_str,
                     "check_expected_npv_minus_floor": p * npv_s + pn * npv_n - e_floor,
                     "check_stress_npv_minus_floor": npv_s - s_floor}}

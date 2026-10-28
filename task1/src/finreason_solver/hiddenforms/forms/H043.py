"""H043 (decimal, percent): maximum pre-tax cost of debt under a WACC ceiling.

The reading:
* WACC = E/(E+D) x re + D/(E+D) x rd x (1 - T), with re and the ceiling in
  percent and T a ratio.
* "maximum pre-tax cost of debt that keeps its WACC at that ceiling": WACC is
  increasing in rd, so the maximum sets WACC = ceiling:
  rd = (ceiling x (E+D) - E x re) / (D x (1 - T)), in percent.
  Equivalently rd = (ceiling x (1 + D/E) - re) / ((D/E) x (1 - T)).
* Report as a percentage: re and ceiling are already percentages, so rd is too.
Slot debt_to_equity_checkpoint = D / E (ratio).
"""
from hlib import num

KEY = "H043"


def solve(b):
    e, d, re_pct, tax = num(b, "A company has equity value {N}, debt value {N}, cost of equity percentage {N}, and corporate tax rate ratio {N}.")
    ceil_pct = num(b, "The WACC ceiling {N} is also a percentage.")
    de = d / e
    rd_pct = (ceil_pct * (1 + de) - re_pct) / (de * (1 - tax))
    wacc_check = e / (e + d) * re_pct + d / (e + d) * rd_pct * (1 - tax)
    return {"final": rd_pct,
            "slots": {"debt_to_equity_checkpoint": de},
            "info": {"wacc_check_minus_ceiling": wacc_check - ceil_pct}}

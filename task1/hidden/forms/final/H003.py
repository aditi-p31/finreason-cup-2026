"""H003 (decimal, percent): shared-cost split that equalises after-tax margins.

The reading, clause by clause:
* Segment S has revenue R_S, pre-shared-cost pre-tax margin m_S and tax rate t_S,
  so its pre-shared-cost pre-tax profit is R_S * m_S.
* A fraction x of the shared pool C goes to A and (1 - x) to B, exactly once.
* After-tax profit of A = (R_A * m_A - x * C) * (1 - t_A); of B =
  (R_B * m_B - (1 - x) * C) * (1 - t_B).  "Each tax rate is applied to the
  resulting positive pre-tax profit", so no loss branch (info records both
  pre-tax profits so positivity can be checked).
* After-tax profit margin ratio = after-tax profit / own revenue.
* Setting the two margins equal is linear in x:
    (1-t_A)(m_A - x C/R_A) = (1-t_B)(m_B - (1-x) C/R_B)
    x = [(1-t_A) m_A - (1-t_B) m_B + (1-t_B) C/R_B] / [(1-t_A) C/R_A + (1-t_B) C/R_B]
* Final: "What percentage x" -> x * 100 (unit percent).
Slots: "shared cost pool as a ratio of Segment A revenue" = C / R_A, and the
same for B = C / R_B (unit ratio).
"""
from hlib import num

KEY = "H003"


def solve(b):
    ra, ma, ta = num(b, "Segment A has revenue {N}, pre-shared-cost pre-tax profit margin {N}, and tax rate {N}.")
    rb, mb, tb = num(b, "Segment B has revenue {N}, pre-shared-cost pre-tax profit margin {N}, and tax rate {N}.")
    c = num(b, "one shared deductible cost pool of {N}.")
    ka, kb = 1 - ta, 1 - tb
    burden_a = c / ra
    burden_b = c / rb
    x = (ka * ma - kb * mb + kb * burden_b) / (ka * burden_a + kb * burden_b)
    pre_a = ra * ma - x * c
    pre_b = rb * mb - (1 - x) * c
    margin_a = pre_a * ka / ra
    margin_b = pre_b * kb / rb
    return {
        "final": x * 100,
        "slots": {
            "segment_a_shared_cost_burden_ratio_checkpoint": burden_a,
            "segment_b_shared_cost_burden_ratio_checkpoint": burden_b,
        },
        "info": {"x": x, "pretax_a": pre_a, "pretax_b": pre_b,
                 "margin_a": margin_a, "margin_b": margin_b},
    }

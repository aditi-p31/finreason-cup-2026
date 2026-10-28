"""H020 (decimal, percent): cooperation credit that exhausts the remedy cap.

The reading:
* Maximum total remedy M, of which fixed interest I.  The cap amount
  available for penalty is M - I (slot penalty_cap_checkpoint, USD).
* Gain-based penalty = realized gain * multiplier; alternative statutory
  floor S.  Pre-credit base = max(gain * multiplier, S) ("the greater of
  those two amounts").
* Credited penalty = (1 - c) * base.  Solve (1 - c) * base + I = M, so
  c = 1 - (M - I) / base.  "What cooperation credit percentage" -> report
  c * 100 (unit percent).  No clamp: the equation is stated as an equality.
"""
from hlib import num

KEY = "H020"


def solve(b):
    m_total, interest = num(b, "The maximum total remedy is {N} USD, of which {N} USD is fixed interest.")
    gain, mult = num(b, "realized gain {N} USD multiplied by {N},")
    floor_amt = num(b, "the alternative statutory floor is {N} USD.")
    gain_pen = gain * mult
    base = max(gain_pen, floor_amt)
    cap = m_total - interest
    c = 1 - cap / base
    return {
        "final": c * 100,
        "slots": {"penalty_cap_checkpoint": cap},
        "info": {"gain_penalty": gain_pen, "floor": floor_amt, "base": base,
                 "credit_ratio": c},
    }

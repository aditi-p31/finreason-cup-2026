"""H030 (decimal, usd): remediation budget with a self-reporting credit.

The reading, clause by clause:
* "Begin with base assessment A."
* "A reporting delay of d days incurs r USD per day": delay charge = d * r.
* "Treat c as the fractional credit applied to the combined assessment and
  delay charge, so the retained fraction is one minus that rate": the credit
  base is A + d * r, retained fraction = 1 - c.
* "Then add mandatory monitoring cost M USD outside the credit base".
* Final total = (A + d * r) * (1 - c) + M (USD).
Slot post_credit_factor_checkpoint: "fraction of the combined assessment
retained after self-reporting credit" = 1 - c (ratio).
"""
from hlib import num

KEY = "H030"


def solve(b):
    base = num(b, "Begin with base assessment {N} USD.")
    days, rate = num(b, "A reporting delay of {N} days incurs {N} USD per day.")
    credit = num(b, "Treat {N} as the fractional credit applied to the combined assessment and delay charge")
    monitor = num(b, "add mandatory monitoring cost {N} USD outside the credit base")
    retained = 1 - credit
    combined = base + days * rate
    total = combined * retained + monitor
    return {
        "final": total,
        "slots": {"post_credit_factor_checkpoint": retained},
        "info": {"combined": combined, "after_credit": combined * retained},
    }

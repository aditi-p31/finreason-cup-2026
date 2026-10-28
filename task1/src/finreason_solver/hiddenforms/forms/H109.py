"""H109 (decimal, usd): inventory carrying amount to sell to hit a quick-ratio target.

The reading:
  target quick ratio k = 1 + uplift.
  selling carrying amount X recovers cash r*X (net of sale costs).
  fraction f of that cash stays in quick assets; the complementary fraction (1-f)
  repays current liabilities at par.
  (Q + f*r*X) / (L - (1-f)*r*X) = k
  => r*X*(f + k*(1-f)) = k*L - Q
  => X = (k*L - Q) / (r * (f + k*(1-f)))
  "minimum ... to reach the required quick ratio exactly" = this root.
Slot liability_relief_weight_checkpoint ("target-weighted liability-repayment
contribution", ratio) = k * (1 - f): the repayment fraction weighted by the
target ratio, the term it contributes to f + k*(1-f).
"""
from hlib import num

KEY = "H109"


def solve(b):
    q, l = num(b, "A company has {N} USD of quick assets excluding inventory and {N} USD of current liabilities")
    up = num(b, "one plus positive uplift ratio {N}.")
    r = num(b, "at net recovery rate {N} of carrying amount")
    f = num(b, "Fraction {N} of the recovered cash remains in quick assets")
    k = 1 + up
    w_liab = k * (1 - f)
    x = (k * l - q) / (r * (f + w_liab))
    cash = r * x
    return {"final": x,
            "slots": {"liability_relief_weight_checkpoint": w_liab},
            "info": {"target_ratio": k, "start_ratio": q / l,
                     "post_ratio": (q + f * cash) / (l - (1 - f) * cash),
                     "post_liabilities": l - (1 - f) * cash}}

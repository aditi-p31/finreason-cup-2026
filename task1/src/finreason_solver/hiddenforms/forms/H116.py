"""H116 (decimal, usd_million): maximum COGS at a required operating margin.

The reading:
* The required operating margin is stated as a percentage figure (no % sign;
  the slot says "Convert the required operating margin from percent to a
  ratio"), so m = stated / 100.
* Operating income = revenue - COGS - operating expenses; exactly meeting the
  margin means operating income = m * revenue, so
  max COGS = revenue * (1 - m) - operating expenses.
* Amounts are already in USD millions; no rescaling.
Slot: m = stated margin / 100 (ratio).
"""
from hlib import num

KEY = "H116"


def solve(b):
    rev, opex, margin_pct = num(b, "Given projected revenue of {N}, operating expenses of {N}, and a required operating margin of {N},")
    m = margin_pct / 100
    cogs = rev * (1 - m) - opex
    return {
        "final": cogs,
        "slots": {"target_margin_ratio_checkpoint": m},
        "info": {"operating_income_target": m * rev},
    }

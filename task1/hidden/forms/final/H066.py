"""H066 (decimal, usd): maximum initial investment meeting a required ROI.

The reading:
* Annual net benefit = energy savings + water savings - maintenance cost.
* PV of net benefits = full-horizon multiplier x annual net benefit.
* ROI = (PV - I) / I.  "maximum initial investment that exactly meets the
  required ROI ratio R": ROI falls as I rises, so the maximum I sets ROI = R:
  I = PV / (1 + R).  R is stated as a ratio, not a percent.
Slot annual_net_benefit_checkpoint = energy + water - maintenance ("annual
savings after maintenance").
"""
from hlib import num

KEY = "H066"


def solve(b):
    energy, water = num(b, "annual energy savings of {N} and annual water savings of {N},")
    maint = num(b, "annual maintenance cost of {N}.")
    mult = num(b, "present-value multiplier for these recurring net benefits is {N}.")
    roi = num(b, "the required ROI ratio {N}.")
    net = energy + water - maint
    pv = mult * net
    inv = pv / (1 + roi)
    return {"final": inv,
            "slots": {"annual_net_benefit_checkpoint": net},
            "info": {"pv_net_benefits": pv, "roi_check": (pv - inv) / inv}}

"""H012 (decimal, usd): whale-transfer excess over a branch-selected threshold.

The reading, clause by clause:
* single-transfer threshold = rolling threshold * (1 - haircut ratio)
  ("the single-transfer threshold is the rolling threshold times
  (1-single-threshold haircut ratio)").
* concentration = current transfer / total activity, where total activity is
  the stated horizon total (a given number, NOT the sum of the three transfers).
* "If it is at least K, including exact equality" -> concentration >= K
  (inclusive).  Then final = current transfer - single-transfer threshold.
* otherwise final = (current + prior1 + prior2) - rolling threshold: "the
  three-transfer total" is the sum of the three named transfers, and the
  threshold is the unadjusted rolling one.
* "excess" is reported as the signed difference; the text states no floor.
Slot single_threshold_retention_checkpoint: "the retained fraction used to
derive the concentrated-transfer threshold" = 1 - haircut ratio.

Adjudication (batch 9, 2026-09-27): readers agreed on draws 1 and 2 and on the
slot, and differed only on draw 3's otherwise arm (A: 1079 - 975 = 104.00, B:
total activity 1213 - 975 = 238.00).  Reader A's reading is kept.  (1) The
text names two different quantities, "total activity over the monitoring
horizon" and "the three-transfer total".  The first is said to *include* the
three transfers, and on every draw it is larger than their sum (1314 vs 1191,
1228 vs 1073.975, 1213 vs 1079), so it also covers other horizon activity.
"Three-transfer total" literally means the sum of the three named transfers.
(2) Under B's reading the two prior transfer amounts are never used on any
arm.  (3) A rolling-window threshold is naturally compared with the
rolling-window (three-transfer) activity, while the horizon total is used only
for the concentration ratio, as the text says.  On draw 3 the two
denominators also select different branches (876/1213 < 0.8 but
876/1079 >= 0.8), which shows the generator separates the two totals on
purpose.
"""
from hlib import num

KEY = "H012"


def solve(b):
    cur, p1, p2 = num(b, "A wallet makes a current transfer of {N} USD after prior transfers of {N} USD and {N} USD")
    roll = num(b, "Its rolling-window whale threshold is {N} USD")
    hc = num(b, "this threshold is reduced by haircut ratio {N},")
    total = num(b, "including all three transfers, is {N} USD")
    k = num(b, "If it is at least {N}, including exact equality")

    retain = 1 - hc
    single = roll * retain
    conc = cur / total
    three_total = cur + p1 + p2
    if conc >= k:
        final = cur - single
    else:
        final = three_total - roll
    return {"final": final,
            "slots": {"single_threshold_retention_checkpoint": retain},
            "info": {"concentration": conc, "cutoff": k,
                     "branch": "single" if conc >= k else "rolling",
                     "single_threshold": single, "three_total": three_total}}

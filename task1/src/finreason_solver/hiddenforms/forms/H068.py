"""H068 (decimal, percent): share of the gross mechanical turnover uplift offset by the sales-loss drag.

Reading:
* post-action asset base A1 is given; "the true reduction from the pre-action
  total-asset base" is R, so pre-action base A0 = A1 + R.
* sales fall by fraction s (no sales level is given, so s is a proportion);
  pre sales S (any positive level; it cancels), post sales S(1 - s).
* pre-action turnover T0 = S / A0; actual post-action turnover T1 = S(1 - s) / A1.
* gross mechanical uplift: the asset-base reduction ALONE, sales held at S:
  U = S / A1 - T0.
* sales-loss drag: the turnover lost because sales fall, on the post-action
  base: D = S / A1 - S(1 - s) / A1 = s S / A1.  U - D is then exactly the net
  turnover change T1 - T0, which is what "gross" uplift "offset by" a drag means.
* answer = D / U, reported as a percentage (x 100) = s * A0 / R * 100.
* Slot pre_action_asset_base_checkpoint: comparable total-asset base before the
  disposal = A1 + R (USD).

Adjudication (batch 6): readers disagreed on the drag.  Reader B measured the
sales loss in isolation on the pre-action base (D' = s S / A0, answer
s * A1 / R * 100).  Decided for the reading above, from the wording alone:
"gross ... uplift" is set against a net, and "offset by the sales-loss drag"
names the only other change between the two compared states, so gross minus
drag must equal the actual before/after turnover change.  "alone" is attached
only to the asset-base reduction ("would create", hypothetical), while the
sales loss "creates" the drag on the actual post-action state.  Under D' the
gross less the drag does not reconcile to the actual change (it leaves an
interaction term s * R / A1).  The normalisation "relative to pre-action
asset turnover" cancels in the ratio under either reading.
"""
from hlib import num

KEY = "H068"


def solve(b):
    a1 = num(b, "it retains a net total-asset base of {N}, while")
    red = num(b, "while {N} is the true reduction from the pre-action total-asset base")
    s = num(b, "Comparable run-rate net sales fall by {N}.")
    a0 = a1 + red
    sales = 1  # sales level cancels in the ratio
    t0 = sales / a0
    uplift = sales / a1 - t0
    t1 = sales * (1 - s) / a1
    drag = sales / a1 - t1
    assert uplift - drag == t1 - t0
    return {"final": drag / uplift * 100,
            "slots": {"pre_action_asset_base_checkpoint": a0},
            "info": {"uplift_per_unit_sales": uplift, "drag_per_unit_sales": drag,
                     "alt_isolated_drag_pct": s * a1 / red * 100}}

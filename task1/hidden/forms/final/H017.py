"""H017 (enum): capital pass / fail under the larger of two stress losses.

The reading, clause by clause:
* joint scenario rate = market shock x market sensitivity
  + credit shock x credit sensitivity (the two "linear loss rates")
  + interaction coefficient x (market shock x credit shock).
  "their product" is read as the product of the two shock ratios: the compound
  subject of the sentence is "market shock ratio ... and credit shock ratio ...",
  and the alternative scenario is likewise stated on the shock ratio itself.
  The other grammatical candidate (product of the two linear loss rates) is
  recorded in info as joint_rate_alt_lossrate_product; on all three draws it
  gives the same label, so only the slot depends on this reading.
* alternative scenario rate = shock ratio^2 x multiplier.
* each rate x portfolio value = dollar loss; use the larger loss.
* remaining capital = available capital - larger loss.
* "meets the minimum" -> remaining >= minimum (inclusive) -> capital_pass,
  otherwise capital_fail.
Slot joint_rate_checkpoint = the total joint-scenario loss ratio (linear rates
plus interaction rate), as a ratio.

Adjudication (batch 2): readers agreed on every label and disagreed only on the
slot. Reader B read "their product" as K x (shock x sens) x (shock x sens).
Reader A's reading is kept: (1) "their" takes the compound subject, whose head
nouns are "market shock ratio" and "credit shock ratio" ("with sensitivity" only
modifies each one); (2) "linear" contrasts with a second-order term in the
shocks, giving the model beta_m*s_m + beta_c*s_c + k*s_m*s_c; (3) the same
sentence's alternative scenario uses the raw shock ratio squared times a
multiplier, with no sensitivity, the same shape as k*s_m*s_c. Under B's reading
the "interaction rate" would be about 1% of the linear rates. The label does not
depend on this choice on any draw.
"""
from hlib import num

KEY = "H017"


def solve(b):
    v = num(b, "A portfolio worth {N} has available capital")
    cap, keep = num(b, "has available capital {N} and must retain at least {N}.")
    ms, msens, cs, csens = num(
        b, "market shock ratio {N} with sensitivity {N} and credit shock ratio {N} with sensitivity {N} contribute")
    k = num(b, "their product times {N} contributes an interaction rate")
    alt_shock, alt_mult = num(b, "shock ratio {N} is squared and multiplied by {N}.")
    linear = ms * msens + cs * csens
    joint_rate = linear + k * ms * cs
    alt_rate = alt_shock * alt_shock * alt_mult
    joint_loss = joint_rate * v
    alt_loss = alt_rate * v
    loss = max(joint_loss, alt_loss)
    remaining = cap - loss
    label = "capital_pass" if remaining >= keep else "capital_fail"
    alt_joint = linear + k * (ms * msens) * (cs * csens)
    alt_remaining = cap - max(alt_joint * v, alt_loss)
    return {"final": label,
            "slots": {"joint_rate_checkpoint": joint_rate},
            "info": {"joint_loss": joint_loss, "alt_loss": alt_loss, "remaining": remaining,
                     "minimum": keep, "margin": remaining - keep,
                     "joint_rate_alt_lossrate_product": alt_joint,
                     "label_under_alt_reading":
                         "capital_pass" if alt_remaining >= keep else "capital_fail"}}

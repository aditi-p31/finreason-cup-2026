"""H009 (decimal, usd): routed network receipt.

Reading, clause by clause:
* Network A "deducts fee ratio fa and then fixed fee ka":
  receipt_A = amount * (1 - fa) - ka.
* Network B "deducts fee ratio fb, then fixed fee kb, and finally increases the
  post-fee amount by bonus ratio bon":
  receipt_B = (amount * (1 - fb) - kb) * (1 + bon).
* "use Network A if its net receipt is at least T USD, including exact
  equality; otherwise use Network B": A when receipt_A >= T (inclusive), else B.
* Slot network_b_after_ratio_fee_checkpoint: B after its proportional fee and
  before its fixed fee and bonus = amount * (1 - fb).
All amounts in USD; no percent conversion.
"""
from hlib import num

KEY = "H009"


def solve(b):
    amt = num(b, "A transfer of {N} USD may use")
    fa, ka = num(b, "Network A deducts fee ratio {N} and then fixed fee {N} USD.")
    fb, kb = num(b, "Network B deducts fee ratio {N}, then fixed fee {N} USD, and finally")
    bon = num(b, "increases the post-fee amount by bonus ratio {N}.")
    thr = num(b, "use Network A if its net receipt is at least {N} USD, including exact equality")
    ra = amt * (1 - fa) - ka
    b_after_ratio = amt * (1 - fb)
    rb = (b_after_ratio - kb) * (1 + bon)
    final = ra if ra >= thr else rb
    return {"final": final,
            "slots": {"network_b_after_ratio_fee_checkpoint": b_after_ratio},
            "info": {"receipt_a": ra, "receipt_b": rb, "threshold": thr,
                     "margin_a_minus_thr": ra - thr, "chose": "A" if ra >= thr else "B"}}

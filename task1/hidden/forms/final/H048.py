"""H048 (percent): required recovery rate after a downturn.

The reading: post-downturn revenue = start revenue * (1 - downturn ratio);
required recovery rate = (target - post) / post ("additional revenue needed
divided by post-downturn revenue"), reported as a percentage (* 100).
Slot post_downturn_checkpoint ("revenue immediately after the downturn", usd)
= start revenue * (1 - downturn ratio).
"""
from hlib import num

KEY = "H048"


def solve(b):
    rev, down = num(b, "starts with revenue {N} and then experiences a downturn ratio {N}.")
    target = num(b, "must reach target revenue {N} after recovery")
    post = rev * (1 - down)
    rate = (target - post) / post
    return {"final": rate * 100,
            "slots": {"post_downturn_checkpoint": post},
            "info": {"target_minus_post": target - post}}

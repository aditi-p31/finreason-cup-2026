"""H042 (decimal, usd): expected net merchant proceeds with one backup retry.

The reading (all counts are exact expectations):
* N original attempts, each for amount A.  Primary success probability p1,
  backup conditional success probability p2.
* Primary failures = N (1 - p1); each triggers exactly one retry, so
  retries = N (1 - p1).  Retry successes = N (1 - p1) p2.  Terminal failures
  (both attempts fail) = N (1 - p1)(1 - p2).
* Settled revenue = A x N (p1 + (1 - p1) p2).
* Primary fees = N x (rate1 A + fixed1) (every original attempt).
* Backup fees = retries x (rate2 A + fixed2) (every retry).
* Handling = h1 x primary failures + h2 x terminal failures.
* Subscription S once.
* Net = revenue - primary fees - backup fees - handling - S.
Slots:
* retry_success_fraction_checkpoint = (1 - p1) p2, the fraction of original
  attempts that settle through the backup retry.
* backup_processing_fees_checkpoint = retries x (rate2 A + fixed2).
* terminal_failure_cost_checkpoint = h2 x terminal failures (the "additional"
  cost incurred for every order where both attempts fail).
"""
from hlib import num

KEY = "H042"


def solve(b):
    n, amt = num(b, "A merchant has {N} original payment attempts, each for {N}.")
    p1 = num(b, "The primary processor succeeds with probability {N}.")
    p2 = num(b, "whose conditional success probability is {N}.")
    r1, k1 = num(b, "The primary charges {N} of the stated amount plus fixed fee {N} on every original attempt")
    r2, k2 = num(b, "The backup charges {N} of the stated amount plus fixed fee {N} on every retry")
    h1, h2, sub = num(b, "The merchant also incurs {N} for every primary failure and an additional {N} for every order where both attempts fail, and pays {N} once for the batch.")
    prim_fail = n * (1 - p1)
    retries = prim_fail
    retry_frac = (1 - p1) * p2
    terminal = prim_fail * (1 - p2)
    revenue = amt * n * (p1 + retry_frac)
    prim_fees = n * (r1 * amt + k1)
    back_fees = retries * (r2 * amt + k2)
    term_cost = h2 * terminal
    handling = h1 * prim_fail + term_cost
    net = revenue - prim_fees - back_fees - handling - sub
    return {"final": net,
            "slots": {"retry_success_fraction_checkpoint": retry_frac,
                      "backup_processing_fees_checkpoint": back_fees,
                      "terminal_failure_cost_checkpoint": term_cost},
            "info": {"revenue": revenue, "primary_fees": prim_fees, "handling": handling}}

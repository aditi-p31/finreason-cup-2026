"""H080 (decimal, percent): two-order (Shapley) attribution of procurement savings.

The reading, clause by clause:
* P = procurement-only savings, T = IT-only savings, C = combined savings.
* Procurement's marginal contribution when introduced first = P.
* When introduced after IT = C - T.
* "giving equal weight" to both orders: attribution = (P + (C - T)) / 2.
* "What percentage of combined-program savings" = attribution / C * 100.
Slot: procurement_marginal_after_it = C - T (usd_million, already in USD
millions in the text, no rescaling).
"""
from hlib import num

KEY = "H080"


def solve(b):
    p, t, c = num(b, "a procurement program alone would deliver {N} USD millions of savings, an IT program alone "
                     "would deliver {N} USD millions, and implementing both would deliver {N} USD millions.")
    after_it = c - t
    attributed = (p + after_it) / 2
    return {
        "final": attributed / c * 100,
        "slots": {"procurement_marginal_after_it_checkpoint": after_it},
        "info": {"attributed": attributed},
    }

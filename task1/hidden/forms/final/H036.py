"""H036 (decimal, percent): after-tax net captured synergy as % of headline sum.

The reading, clause by clause:
* headline sum H = procurement + IT + revenue-synergy contribution (USD millions).
* "Each pairwise overlap includes the same common three-way overlap T", so the
  three pairwise overlaps are the ordinary pairwise intersections and
  inclusion-exclusion gives the deduplicated amount
      D = H - (PI + PR + IR) + T.
* realized = ratio * D.
* "Deduct fully tax-deductible annual integration charge C from the positive
  realized amount before applying tax rate tau": pre-tax net = realized - C,
  after-tax net = (realized - C) * (1 - tau).
* "What percentage of the unadjusted headline sum remains": final =
  after-tax net / H * 100 (percent unit, so the ratio is multiplied by 100).

Slots:
* headline_savings_checkpoint = H (the unadjusted headline sum).
* pairwise_overlap_checkpoint = PI + PR + IR, the pairwise sum before the
  three-way overlap is added back.
"""
from hlib import num

KEY = "H036"


def solve(b):
    proc, it, rev = num(
        b,
        "procurement savings {N}, IT savings {N}, and revenue-synergy contribution {N},",
    )
    pi, pr, ir = num(
        b,
        "procurement-IT overlap {N}, procurement-revenue overlap {N}, and IT-revenue overlap {N}.",
    )
    triple = num(b, "the same common three-way overlap {N}.")
    ratio = num(b, "then realize ratio {N} of that deduplicated amount")
    charge = num(b, "annual integration charge {N} from the positive realized amount")
    tax = num(b, "before applying tax rate {N}.")

    headline = proc + it + rev
    pairwise = pi + pr + ir
    dedup = headline - pairwise + triple
    realized = ratio * dedup
    pretax_net = realized - charge
    after_tax = pretax_net * (1 - tax)
    final = after_tax / headline * 100
    return {
        "final": final,
        "slots": {
            "headline_savings_checkpoint": headline,
            "pairwise_overlap_checkpoint": pairwise,
        },
        "info": {"dedup": dedup, "realized": realized, "pretax_net": pretax_net,
                 "after_tax": after_tax},
    }

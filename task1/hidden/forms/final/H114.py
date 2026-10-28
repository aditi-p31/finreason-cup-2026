"""H114 (decimal, usd): minimum total income covering outlays plus a savings share.

The reading, clause by clause:
* cash commitments = essential + discretionary + emergency-reserve contribution.
* savings = s * income, a separate commitment on top of the cash ones.
* minimum income I solves I = commitments + s * I  =>  I = commitments / (1 - s).
Slot cash_needs_checkpoint: "the combined cash commitments before solving for
income" = essential + discretionary + reserve (the savings share is a fraction
of the unknown income, so it is not part of the pre-solve sum).
"""
from hlib import num

KEY = "H114"


def solve(b):
    ess, disc, res = num(b, "must cover essential outlays of {N}, planned discretionary outlays of {N}, and an emergency-reserve contribution of {N} while")
    s = num(b, "while also saving {N} of total income")

    needs = ess + disc + res
    income = needs / (1 - s)
    return {"final": income,
            "slots": {"cash_needs_checkpoint": needs},
            "info": {"check_residual": income - needs - s * income}}

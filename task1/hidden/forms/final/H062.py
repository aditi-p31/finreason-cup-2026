"""H062 (decimal, ratio): exit-quote threshold for a target net return.

The reading, clause by clause (capital K cancels; quotes are reporting-currency
units per base-currency unit):
* entry: base = K / q_entry x (1 - f_entry).
* exit: reporting = base x q_exit x (1 - f_exit).
* net = reporting - c x K (financing charge c times initial capital).
* net return = net / K - 1 = R.
So q_exit x (1 - f_entry)(1 - f_exit) / q_entry = 1 + R + c and
q_exit = (1 + R + c) x q_entry / ((1 - f_entry)(1 - f_exit)).
Slot gross_growth_checkpoint = the return-and-carry gross growth multiple
= 1 + R + c, the gross exit value per unit of initial capital needed to cover the
target return plus the financing carry (equal, at the threshold, to
q_exit x (1 - f_entry)(1 - f_exit) / q_entry; both are recorded in info).
"""
from hlib import num

KEY = "H062"


def solve(b):
    q_in = num(b, "at normalized entry quote {N}, expressed as")
    f_in = num(b, "The entry conversion retains one minus fee ratio {N}.")
    f_out = num(b, "to be solved for and retain one minus fee ratio {N}.")
    c = num(b, "financing charge equal to {N} times the initial")
    ret = num(b, "at which the net return equals {N}.")
    gross = 1 + ret + c
    q_out = gross * q_in / ((1 - f_in) * (1 - f_out))
    check = q_out * (1 - f_in) * (1 - f_out) / q_in
    return {"final": q_out,
            "slots": {"gross_growth_checkpoint": gross},
            "info": {"gross_from_threshold": check,
                     "net_return_check": check - c - 1}}

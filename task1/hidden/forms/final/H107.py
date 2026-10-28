"""H107 (enum): two closed FX routes with fees, fixed costs and a return hurdle.

The reading, clause by clause:
* K = starting USD capital.
* Route A: USD->X->Y->USD with rates "X per USD", "Y per X", "USD per Y";
  gross multiplier mA = product of the three rates.
* Route B: USD->Z->USD with "Z per USD", "USD per Z"; mB = product of the two.
* "apply its single aggregate proportional fee fA or fB once to final USD
  proceeds, then subtract fixed USD cost cA or cB": the pairs are listed in
  route order (A first, B second).  terminal_R = K * m_R * (1 - f_R) - c_R.
* "qualifies only if its exact terminal value meets return hurdle h on starting
  capital": (terminal - K) / K >= h, i.e. terminal >= K * (1 + h).  "meets" is
  inclusive (>=).
* choose the qualifying route with the higher exact terminal value; Route A on
  an exact tie when both qualify; the sole qualifier; else "No trade".

Slots: a_gross_multiplier_checkpoint = mA; b_gross_multiplier_checkpoint = mB.
"""
from hlib import num, pick_two

KEY = "H107"


def solve(b):
    cap = num(b, "Starting with USD capital {N},")
    xa, ya, ua = num(b, "{N} is X per USD, {N} is Y per X, and {N} is USD per Y.")
    zb, ub = num(b, "{N} is Z per USD and {N} is USD per Z.")
    fee_a, fee_b = num(b, "aggregate proportional fee {N} or {N} once")
    cost_a, cost_b = num(b, "subtract fixed USD cost {N} or {N}.")
    hurdle = num(b, "meets return hurdle {N} on starting capital.")

    m_a = xa * ya * ua
    m_b = zb * ub
    term_a = cap * m_a * (1 - fee_a) - cost_a
    term_b = cap * m_b * (1 - fee_b) - cost_b
    need = cap * (1 + hurdle)
    ok_a = term_a >= need
    ok_b = term_b >= need
    label = pick_two(ok_a, ok_b, term_a, term_b, a="Route A", b="Route B",
                     neither="No trade", better="higher", tie="Route A")
    return {
        "final": label,
        "slots": {"a_gross_multiplier_checkpoint": m_a,
                  "b_gross_multiplier_checkpoint": m_b},
        "info": {"terminal_a": term_a, "terminal_b": term_b, "hurdle_value": need,
                 "ok_a": ok_a, "ok_b": ok_b},
    }

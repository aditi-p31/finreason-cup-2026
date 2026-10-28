"""H083 (enum): current sale versus hold-then-sell of a two-lot position.

The reading:
* Shares N = n1 + n2; complete two-lot basis = n1 x b1 + n2 x b2 (total USD).
* "sale cost reduces amount realized": amount realized = N x price - total sale cost.
* Gain = amount realized - basis; tax = gain ratio x gain only when the gain is
  positive ("no loss credit"), so taxable gain = max(gain, 0).
* Current after-tax cash = amount realized(now) - gain ratio x taxable gain(now).
* Each future state (base, downside): after-tax cash = amount realized(state)
  - gain ratio x taxable gain(state) + N x dividend x (1 - dividend tax ratio).
  The dividend is gross per share, taxed at its own ratio, and is not part of
  amount realized (the gain is amount realized minus basis only).
* PV(state) = after-tax cash(state) / (1 + rate), one period.
* Expected PV = p_down x PV(down) + (1 - p_down) x PV(base).
* Current qualifies: current after-tax cash >= floor ("at least").
  Hold qualifies: PV(down) >= floor ("at least").
* Both qualify: higher of expected PV and current cash, Current sale on an exact
  tie.  One qualifies: it.  Otherwise Neither.
Slots: current, base-state and downside-state taxable gains (max(gain, 0));
every draw's gains are positive, so this equals the raw gain there.
"""
from hlib import num, pick_two, pos

KEY = "H083"


def solve(b):
    n1, b1, n2, b2 = num(b, "An investor owns {N} shares bought at {N} per share and {N} shares bought at {N} per share.")
    p0, c0 = num(b, "selling the complete position now at {N} per share with total sale cost {N},")
    p_base = num(b, "The base terminal sale price is {N},")
    p_down = num(b, "the downside terminal sale price is {N},")
    div = num(b, "gross terminal dividend is {N} per share in either state")
    c1 = num(b, "total future sale cost is {N} in either state.")
    g_tax = num(b, "gain tax ratio {N} applies to each generated positive gain.")
    d_tax = num(b, "Terminal dividend tax ratio is {N}.")
    rate = num(b, "one period using time-value-only rate {N}.")
    q_down = num(b, "Assign subjective downside probability {N} and base probability one minus that value.")
    cur_floor = num(b, "Current sale qualifies when its exact after-tax cash is at least {N}.")
    hold_floor = num(b, "Holding qualifies when exact downside-state present value is at least {N}.")

    n = n1 + n2
    basis = n1 * b1 + n2 * b2
    div_net = n * div * (1 - d_tax)

    ar0 = n * p0 - c0
    tg0 = pos(ar0 - basis)
    cash0 = ar0 - g_tax * tg0

    def state(price):
        ar = n * price - c1
        tg = pos(ar - basis)
        cash = ar - g_tax * tg + div_net
        return tg, cash / (1 + rate)

    tg_base, pv_base = state(p_base)
    tg_down, pv_down = state(p_down)
    exp_pv = q_down * pv_down + (1 - q_down) * pv_base

    ok_cur = cash0 >= cur_floor
    ok_hold = pv_down >= hold_floor
    label = pick_two(ok_cur, ok_hold, cash0, exp_pv, a="Current sale", b="Hold then sell",
                     neither="Neither", better="higher", tie="Current sale")
    return {"final": label,
            "slots": {"current_gain_checkpoint": tg0,
                      "base_gain_checkpoint": tg_base,
                      "downside_gain_checkpoint": tg_down},
            "info": {"current_cash": cash0, "current_margin": cash0 - cur_floor,
                     "pv_down": pv_down, "hold_margin": pv_down - hold_floor,
                     "pv_base": pv_base, "expected_pv": exp_pv,
                     "raw_gain_now": ar0 - basis}}

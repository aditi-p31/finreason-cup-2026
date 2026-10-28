"""H051 (enum Call/Put/Neither): two-state call vs put qualification.

The reading:
  * bull price Su with probability p, bear price Sd with probability 1 - p.
  * call (strike Kc): bull payoff Su - Kc, bear payoff 0.
    put  (strike Kp): bull payoff 0,      bear payoff Kp - Sd.
  * expected profit = probability-weighted payoff minus premium, subtracted once:
    call EP = p * (Su - Kc) + (1 - p) * 0 - Cprem; put EP = p * 0 + (1 - p) * (Kp - Sd) - Pprem.
  * worst-state profit = min over the two states of payoff - premium.
  * qualifies iff EP >= min_EP AND worst >= min_worst ("at least" -> >= on both).
  * choose the qualifying strategy with higher EP; exact tie -> Call ("choose Call
    on an exact tie"); sole qualifier wins; neither qualifies -> Neither.
Slots: call_payoff_checkpoint = Su - Kc (positive bull-state call payoff);
put_payoff_checkpoint = Kp - Sd (positive bear-state put payoff).
"""
from hlib import num, pick_two

KEY = "H051"


def solve(b):
    su, sd, p = num(b, "bullish terminal price {N} and lower bearish terminal price {N}, "
                       "with bullish probability {N}.")
    kc = num(b, "the call with strike {N} pays")
    kp = num(b, "the put with strike {N} pays")
    cprem, pprem = num(b, "Subtract call premium {N} and put premium {N} once")
    min_ep, min_worst = num(b, "exact expected profit is at least {N} and exact "
                               "worst-state profit is at least {N}.")

    call_bull = max(su - kc, 0)
    call_bear = max(sd - kc, 0)
    put_bull = max(kp - su, 0)
    put_bear = max(kp - sd, 0)

    call_ep = p * call_bull + (1 - p) * call_bear - cprem
    put_ep = p * put_bull + (1 - p) * put_bear - pprem
    call_worst = min(call_bull - cprem, call_bear - cprem)
    put_worst = min(put_bull - pprem, put_bear - pprem)

    ok_call = call_ep >= min_ep and call_worst >= min_worst
    ok_put = put_ep >= min_ep and put_worst >= min_worst
    label = pick_two(ok_call, ok_put, call_ep, put_ep, a="Call", b="Put",
                     neither="Neither", better="higher", tie="Call")
    return {
        "final": label,
        "slots": {"call_payoff_checkpoint": call_bull,
                  "put_payoff_checkpoint": put_bear},
        "info": {"call_ep": call_ep, "put_ep": put_ep, "min_ep": min_ep,
                 "call_worst": call_worst, "put_worst": put_worst,
                 "min_worst": min_worst, "ok_call": ok_call, "ok_put": ok_put,
                 "strikes_strictly_inside": sd < kc < su and sd < kp < su},
    }

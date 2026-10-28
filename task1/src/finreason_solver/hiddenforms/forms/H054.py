"""H054 (decimal, percent): quick-ratio convexity premium across two recovery states.

The reading, clause by clause:
* QA0 = quick assets before the sale excluding inventory; I = inventory carrying
  amount sold.
* recovery rates: r_low stated; r_high = r_low + spread.  Net proceeds in a
  state = r_state * I (recovery rate on the carrying amount sold).
* fraction f of net proceeds remains as cash in quick assets; the complementary
  fraction (1 - f) repays current liabilities at par.
* L_rem = liabilities remaining after high-state repayment, so the implied
  pre-sale liabilities are L0 = L_rem + (1 - f) * r_high * I, used in both
  states.
* state s: QA_s = QA0 + f * r_s * I, L_s = L0 - (1 - f) * r_s * I,
  q_s = QA_s / L_s.
* p = probability of the high state; low state has 1 - p.
* gap = [p * q_high + (1 - p) * q_low]
        - [(p * QA_high + (1 - p) * QA_low) / (p * L_high + (1 - p) * L_low)].
  The question says the first minus the second ("subtract ... from ...").
* "percentage-point equivalent" of a ratio difference: final = gap * 100.

Slots (USD, unrounded here):
* low_state_retained_cash_checkpoint = f * r_low * I, the part of low-state net
  proceeds that "remains as cash in quick assets".
* incremental_retained_cash_checkpoint = f * (r_high - r_low) * I = f * spread * I.
* incremental_repayment_checkpoint = (1 - f) * spread * I.
"""
from hlib import num

KEY = "H054"


def solve(b):
    qa0 = num(b, "Quick assets before the sale, excluding inventory, are {N} USD")
    inv = num(b, "inventory carrying amount {N} USD is sold")
    f = num(b, "fraction {N} of net proceeds remains as cash in quick assets")
    r_low = num(b, "The low recovery rate is {N} and")
    spread = num(b, "plus positive spread {N};")
    p = num(b, "The high state occurs with probability {N}.")
    l_rem = num(b, "the scenario gives {N} USD, the liabilities remaining after high-state repayment")

    r_high = r_low + spread
    repay_share = 1 - f
    l0 = l_rem + repay_share * r_high * inv

    def state(r):
        qa = qa0 + f * r * inv
        liab = l0 - repay_share * r * inv
        return qa, liab, qa / liab

    qa_lo, l_lo, q_lo = state(r_low)
    qa_hi, l_hi, q_hi = state(r_high)

    avg_ratio = p * q_hi + (1 - p) * q_lo
    ratio_of_avgs = (p * qa_hi + (1 - p) * qa_lo) / (p * l_hi + (1 - p) * l_lo)
    gap = avg_ratio - ratio_of_avgs
    return {
        "final": gap * 100,
        "slots": {
            "low_state_retained_cash_checkpoint": f * r_low * inv,
            "incremental_retained_cash_checkpoint": f * spread * inv,
            "incremental_repayment_checkpoint": repay_share * spread * inv,
        },
        "info": {"L0": l0, "q_low": q_lo, "q_high": q_hi, "avg_ratio": avg_ratio,
                 "ratio_of_avgs": ratio_of_avgs, "l_high_check": l_hi},
    }

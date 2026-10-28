"""H091 (enum): expected customer-attrition value loss versus expected tax loss.

The reading, clause by clause:
* Verified recurring EBITDA R; "target-controlled confirmed run-rate savings
  not already included in that amount" S.  The qualifiers (target-controlled,
  confirmed, not already included) are the conditions for adding S, so the
  base-case valuation EBITDA is R + S, valued at the base multiple m_b:
  EV_base = (R + S) * m_b.
* "In a customer-attrition state, recurring EBITDA falls by d and the
  valuation multiple compresses to m_a": only recurring EBITDA falls, the
  target-controlled savings are unaffected, so the attrition-case valuation
  EBITDA is (R - d) + S and EV_attr = (R - d + S) * m_a.
* Expected customer value loss = p * (EV_base - EV_attr).
* Tax: gross exposure X crystallizes with probability q, insurance recovers
  fraction k: uninsured exposure = X * (1 - k); expected tax loss =
  q * X * (1 - k).
* Compare the exact values: attrition larger / tax larger / equal (exact tie).
Slots:
* attrition_case_ebitda_checkpoint: "recurring EBITDA in the customer-attrition
  state".  REVISED 2026-10-19 (the author's decision): R - d.  The question
  defines recurring EBITDA as the verified figure that excludes the savings
  ("not already included in that amount") and says recurring EBITDA "falls by"
  d, so the slot is R - d.  A blind independent re-solve (2026-10-18) read
  R - d, and a blind three-lens referee panel chose R - d 3 to 0.  The final
  label is unchanged: valuations still add S in both states.
  Earlier history: ADJUDICATED (batch 7): reader A filled R - d, reader B filled
  R + S - d.  The adjudicator took R + S - d.  It is the attrition-case EBITDA
  that the attrition-case enterprise value is built on (EV_attr = EBITDA *
  m_a), and the slot id names the "attrition case", matching the text's
  "attrition-case enterprise values".  The confirmed run-rate savings are
  themselves recurring (run-rate), and once added they are part of the
  recurring EBITDA from which the attrition fall is taken.  R - d is an
  intermediate that only a split of the same computation produces.  It is
  recorded in info as attr_recurring_excl_savings.  The final does not
  depend on this choice.
* uninsured_tax_exposure_checkpoint: "tax exposure remaining after insurance
  recovery" = X * (1 - k) (USD millions as stated, not probability weighted).
"""
from hlib import num

KEY = "H091"

A_LARGER = "Customer attrition loss is larger"
T_LARGER = "Tax exposure loss is larger"
EQUAL = "Expected losses are equal"


def solve(b):
    rec, sav = num(b, "verified recurring EBITDA is {N} and target-controlled confirmed run-rate savings not already included in that amount are {N}.")
    m_base = num(b, "The base case applies valuation multiple {N}.")
    drop, m_attr, p = num(b, "In a customer-attrition state, recurring EBITDA falls by {N} and the valuation multiple compresses to {N}; that state occurs with probability {N}.")
    expo, q, rec_frac = num(b, "gross tax exposure of {N} crystallizes with probability {N}, and insurance recovers fraction {N} if it crystallizes.")
    base_ebitda = rec + sav
    attr_recurring = rec - drop
    attr_ebitda = attr_recurring + sav
    ev_base = base_ebitda * m_base
    ev_attr = attr_ebitda * m_attr
    cust_loss = p * (ev_base - ev_attr)
    uninsured = expo * (1 - rec_frac)
    tax_loss = q * uninsured
    if cust_loss > tax_loss:
        label = A_LARGER
    elif tax_loss > cust_loss:
        label = T_LARGER
    else:
        label = EQUAL
    # alternative reading kept for adjudication only: savings excluded from valuation
    alt_cust = p * (rec * m_base - attr_recurring * m_attr)
    return {
        "final": label,
        "slots": {"attrition_case_ebitda_checkpoint": attr_recurring,
                  "uninsured_tax_exposure_checkpoint": uninsured},
        "info": {"ev_base": ev_base, "ev_attr": ev_attr,
                 "attr_recurring_excl_savings": attr_recurring,
                 "customer_loss": cust_loss, "tax_loss": tax_loss,
                 "margin": cust_loss - tax_loss,
                 "alt_customer_loss_savings_excluded": alt_cust},
    }

"""H092 (percent): fictional reconciliation score of two OCF schedules.

The reading, as stated:
  indirect OCF = net income + depreciation + amortization
                 - (increase AR + increase inventory + decrease AP)
                 + increase accrued liabilities + increase income taxes payable
  direct OCF   = operating cash receipts - non-tax operating payments - cash taxes paid
  margin_i = OCF_i / revenue (ratios)
  score = (m_ind + m_dir) / 2 - (m_ind - m_dir)^2, then "Report the score as a
  percentage" -> * 100.  The score is formed on the ratio margins (the margins
  are "normalized by revenue", i.e. ratios) and converted to a percentage only
  at the end.
Slots (usd_million, inputs already in USD millions, no rescale):
  noncash_charges = depreciation + amortization
  working_capital_cash_uses = increase AR + increase inventory + decrease AP
  direct_cash_uses = non-tax operating cash payments + cash income taxes paid
"""
from hlib import num

KEY = "H092"


def solve(b):
    ni = num(b, "starts with after-tax net income {N},")
    dep, amort = num(b, "adds nonoverlapping depreciation {N} and amortization {N},")
    ar = num(b, "an increase in accounts receivable {N},")
    inv = num(b, "an increase in inventory {N},")
    ap = num(b, "a decrease in accounts payable {N},")
    accr = num(b, "an increase in accrued liabilities excluding income taxes payable {N}")
    itp = num(b, "and an increase in income taxes payable {N}.")
    pay, tax = num(b, "subtracts non-tax operating cash payments {N} and cash income taxes paid {N}")
    rec = num(b, "from operating cash receipts {N}.")
    revenue = num(b, "by reported revenue {N}.")
    noncash = dep + amort
    wc = ar + inv + ap
    direct_uses = pay + tax
    ocf_ind = ni + noncash - wc + accr + itp
    ocf_dir = rec - direct_uses
    m_ind = ocf_ind / revenue
    m_dir = ocf_dir / revenue
    diff = m_ind - m_dir
    score = (m_ind + m_dir) / 2 - diff * diff
    return {"final": score * 100,
            "slots": {"noncash_charges_checkpoint": noncash,
                      "working_capital_cash_uses_checkpoint": wc,
                      "direct_cash_uses_checkpoint": direct_uses},
            "info": {"ocf_indirect": ocf_ind, "ocf_direct": ocf_dir,
                     "margin_indirect": m_ind, "margin_direct": m_dir}}

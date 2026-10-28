"""H001 (decimal, usd_million): maximum borrowing that keeps a required current ratio.

The reading, clause by clause:
* Current assets CA and current liabilities CL are given in USD millions.
* "a cash-funded non-current-asset purchase of P, which reduces current assets
  by the purchase amount": CA_post = CA - P.  This is the slot
  post_purchase_assets_checkpoint ("current assets remaining after the planned
  non-current-asset purchase").
* "The required current ratio is one plus the ratio r": R = 1 + r.
* Borrowing D is "added to both cash and current liabilities", so the ratio
  becomes (CA_post + D) / (CL + D).  "maximum ... while exactly meeting the
  required current ratio": (CA_post + D) / (CL + D) = R, solved exactly:
  D = (CA_post - R * CL) / (R - 1).  With R > 1, the ratio falls as D grows, so
  the equality point is the maximum.
* Units: inputs and output are both USD millions; no rescaling.
"""
from hlib import num

KEY = "H001"


def solve(b):
    ca, cl = num(b, "current assets of {N} and current liabilities of {N} in USD millions")
    purchase = num(b, "non-current-asset purchase of {N}, which reduces current assets")
    r = num(b, "The required current ratio is one plus the ratio {N}")
    req = 1 + r
    ca_post = ca - purchase
    borrow = (ca_post - req * cl) / (req - 1)
    return {"final": borrow,
            "slots": {"post_purchase_assets_checkpoint": ca_post},
            "info": {"required_ratio": req,
                     "check_ratio_after": (ca_post + borrow) / (cl + borrow),
                     "ratio_before_borrowing": ca_post / cl}}

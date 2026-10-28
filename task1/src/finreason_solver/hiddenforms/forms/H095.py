"""H095 (decimal, usd_million): signed headroom of a noncash EBITDA add-back.

The reading:
* normalized OCF = reported OCF - working-capital release - tax refund
  ("including a temporary working-capital release of W and a one-time tax
  refund of R that the reviewer removes"; the slot confirms the release is
  removed as well).
* Screen: normalized OCF / (EBITDA + add-back) >= minimum ratio ("at least").
  The add-back has no OCF effect, so the maximum add-back solves the equality:
  A_max = normalized OCF / minimum ratio - EBITDA.
* headroom = A_max - proposed add-back (positive = unused capacity).
Slot: reported OCF - working-capital release (before removing the refund).
"""
from hlib import num

KEY = "H095"


def solve(b):
    ebitda = num(b, "Verified recurring EBITDA before the proposed adjustment is {N}.")
    ocf, wc, refund = num(b, "Reported operating cash flow is {N}, including a temporary working-capital release of {N} and a one-time tax refund of {N} that the reviewer removes.")
    proposed, floor_ratio = num(b, "after the proposed noncash management add-back of {N} to be at least {N}.")

    after_wc = ocf - wc
    norm = after_wc - refund
    a_max = norm / floor_ratio - ebitda
    return {
        "final": a_max - proposed,
        "slots": {"cash_flow_after_working_capital_checkpoint": after_wc},
        "info": {"normalized_ocf": norm, "max_addback": a_max},
    }

"""H053 (decimal, percent): percentage-scaled HHI of three modeled exposures.

The reading:
* P_i = covered volume_i * assessment ratio_i for i = 1, 2, 3.
* s_i = P_i / (P_1 + P_2 + P_3); H = sum s_i^2.
* "Report 100H as a percentage" -> final = 100 * H.
Slots: modeled exposure before normalization of category 1 = P_1 and of
category 2 = P_2 (usd).
"""
from hlib import num

KEY = "H053"


def solve(b):
    v1, r1, v2, r2, v3, r3 = num(
        b,
        "Category 1 has covered volume {N} USD and decimal assessment ratio {N}; "
        "Category 2 has {N} USD and {N}; Category 3 has {N} USD and {N}.",
    )
    p1, p2, p3 = v1 * r1, v2 * r2, v3 * r3
    tot = p1 + p2 + p3
    h = sum((p / tot) * (p / tot) for p in (p1, p2, p3))
    return {
        "final": 100 * h,
        "slots": {
            "category_1_exposure_checkpoint": p1,
            "category_2_exposure_checkpoint": p2,
        },
        "info": {"P3": p3, "total": tot},
    }

"""H096 (decimal, usd): minimum total capital for a buffered high-risk allocation.

The reading, clause by clause:
* high-risk allocation A.
* "Before applying its risk-appetite ratio r, it increases the allocation target
  by diversification buffer ratio d": buffered target = A * (1 + d).
* the risk-appetite ratio r is the share of the allocable capital pool that may
  go to the high-risk allocation, so the minimum allocable pool that supports
  the buffered target is buffered / r.  (Multiplying by r would make the
  required capital smaller than the allocation it must fund, which contradicts
  "minimum total capital required to fund the buffered high-risk allocation".)
* "It also keeps R outside the allocable capital pool": the reserve is added on
  top, not subject to the ratio.
* final = A * (1 + d) / r + R, in USD.

Slot buffered_target_checkpoint = A * (1 + d).
"""
from hlib import num

KEY = "H096"


def solve(b):
    alloc = num(b, "must support a high-risk allocation of {N}.")
    ratio = num(b, "Before applying its risk-appetite ratio {N},")
    buf = num(b, "by diversification buffer ratio {N}.")
    reserve = num(b, "It also keeps {N} outside the allocable capital pool.")
    buffered = alloc * (1 + buf)
    pool = buffered / ratio
    return {
        "final": pool + reserve,
        "slots": {"buffered_target_checkpoint": buffered},
        "info": {"allocable_pool": pool, "reserve": reserve},
    }

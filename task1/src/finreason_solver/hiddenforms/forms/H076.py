"""H076 (decimal, usd_million): signed Tier 1 adjustment meeting capital and leverage.

The reading, clause by clause (the question states both formulas):
* combined_ratio = minimum capital ratio + capital buffer ratio ("Add ...").
* capital gap = combined_ratio * RWA - (Tier1 + Tier2).
* leverage gap = minimum_leverage_ratio * total_exposure - Tier1.
* "Return the larger gap": x = max(capital gap, leverage gap).  Signed; a
  negative x is a permitted withdrawal and is returned as negative.
* units: all amounts USD millions, reported in USD millions.

Slot combined_capital_requirement_ratio_checkpoint = combined_ratio (ratio,
exact value used downstream).
"""
from hlib import num

KEY = "H076"


def solve(b):
    t1, t2, rwa, exposure = num(
        b,
        "eligible Tier 1 capital {N} and eligible Tier 2 capital {N}, "
        "risk-weighted assets {N}, and total exposure {N}, all in USD millions.",
    )
    min_cap, buffer_, min_lev = num(
        b,
        "minimum capital ratio {N}, capital buffer ratio {N}, and minimum leverage ratio {N} as decimal ratios.",
    )
    combined = min_cap + buffer_
    cap_gap = combined * rwa - (t1 + t2)
    lev_gap = min_lev * exposure - t1
    x = max(cap_gap, lev_gap)
    return {
        "final": x,
        "slots": {"combined_capital_requirement_ratio_checkpoint": combined},
        "info": {"capital_gap": cap_gap, "leverage_gap": lev_gap},
    }

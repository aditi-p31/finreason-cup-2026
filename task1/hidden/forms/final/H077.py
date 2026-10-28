"""H077 (decimal, usd_million): minimum opening cash meeting two period-end floors.

The reading, clause by clause:
* opening cash X is carried through both periods; period one adds inflow i1
  and subtracts outflow o1; period two then adds i2 and subtracts o2.
* period-end balances: E1 = X + (i1 - o1); E2 = X + (i1 - o1) + (i2 - o2).
* "Each period-end cash balance must be at least F" -> E1 >= F and E2 >= F.
* minimum X = max(F - (i1 - o1), F - (i1 - o1) - (i2 - o2)).
  All amounts are already in USD millions; no rescaling.

Slot period_one_net_to_floor_ratio_checkpoint "period-one net cash flow as a
fraction of the required cash floor" = (i1 - o1) / F.
"""
from hlib import num

KEY = "H077"


def solve(b):
    i1, o1 = num(b, "Period one has cash inflow {N} and cash outflow {N}.")
    i2, o2 = num(b, "Period two then has cash inflow {N} and cash outflow {N}.")
    floor = num(b, "Each period-end cash balance must be at least {N}.")
    net1 = i1 - o1
    net2 = i2 - o2
    need1 = floor - net1
    need2 = floor - net1 - net2
    final = max(need1, need2)
    return {
        "final": final,
        "slots": {"period_one_net_to_floor_ratio_checkpoint": net1 / floor},
        "info": {"need_p1": need1, "need_p2": need2},
    }

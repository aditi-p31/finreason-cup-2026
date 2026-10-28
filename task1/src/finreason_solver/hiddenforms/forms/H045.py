"""H045 (enum): ESG program selection by net cost per effective ton.

The reading:
  effective reduction = verified reduction * (1 - overlap ratio)
  net cost per effective ton = (cost - financial benefit) / effective reduction
  feasible iff cost <= cap ("does not exceed" -> <=) and
               effective reduction >= floor ("reaches" -> >=)
  both feasible -> lower net cost per ton, program_a on an exact tie;
  one feasible -> that one; neither -> no_feasible_program.
Slot program_a_net_cost_checkpoint ("program A net cost after financial
benefits", usd) = cost_A - benefit_A.
"""
from hlib import num, pick_two

KEY = "H045"


def solve(b):
    ca, ba, va, oa = num(b, "Compare ESG program A, with cost {N}, financial benefit {N}, "
                            "verified emissions reduction {N}, and attribution-overlap ratio {N},")
    cb, bb, vb, ob = num(b, "against program B with cost {N}, financial benefit {N}, "
                            "verified emissions reduction {N}, and attribution-overlap ratio {N}.")
    cap = num(b, "its cost does not exceed {N}")
    floor_ = num(b, "its effective reduction reaches {N}.")
    ea = va * (1 - oa)
    eb = vb * (1 - ob)
    na = (ca - ba) / ea
    nb = (cb - bb) / eb
    ok_a = ca <= cap and ea >= floor_
    ok_b = cb <= cap and eb >= floor_
    label = pick_two(ok_a, ok_b, na, nb, a="program_a", b="program_b",
                     neither="no_feasible_program", better="lower", tie="program_a")
    return {"final": label,
            "slots": {"program_a_net_cost_checkpoint": ca - ba},
            "info": {"eff_a": ea, "eff_b": eb, "npt_a": na, "npt_b": nb,
                     "ok_a": ok_a, "ok_b": ok_b, "cap": cap, "floor": floor_}}

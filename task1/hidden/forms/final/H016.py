"""H016 (decimal, percent): smoothed-growth drag x uplift product index.

The reading, clause by clause:
* One initial contribution C0 at the start of the horizon ("receives C0 USD at
  the start of two equal phases"), and one boundary contribution C1 added at
  the phase boundary.  Each phase lasts n whole annual compounding periods.
* Actual path: phase-one factor (1 + r1) per period, phase-two factor (1 + r2).
  Actual terminal of C0 = C0 * (1+r1)^n * (1+r2)^n; actual terminal of C1 =
  C1 * (1+r2)^n (it only lives through phase two).
* Smoothed counterfactual: "the arithmetic mean of the two annual growth
  factors" g = ((1+r1) + (1+r2)) / 2, used in both phases, contribution dates
  preserved.  Smoothed terminal of C0 = C0 * g^(2n); of C1 = C1 * g^n.
* initial-contribution drag = smoothed terminal(C0) - actual terminal(C0).
  boundary-contribution uplift = actual terminal(C1) - smoothed terminal(C1).
* Each difference is divided by the nominal undiscounted sum of contributed
  cash S = C0 + C1; the two ratios are multiplied once; the product is
  converted to percent (x 100).  Rounded only at the end by run_forms.

Slots:
* first_phase_growth_checkpoint "actual first-phase compound growth factor"
  = (1 + r1)^n.
* smoothed_phase_growth_checkpoint "one-phase compound growth factor under the
  smoothed counterfactual" = g^n.
"""
from hlib import num, ipow

KEY = "H016"


def solve(b):
    c0, n = num(b, "An account receives {N} USD at the start of two equal phases, "
                   "each lasting {N} whole annual compounding periods.")
    r1, r2, c1 = num(b, "The first-phase annual rate ratio is {N}, the strictly higher "
                        "second-phase rate ratio is {N}, and {N} USD is added at the phase boundary.")
    g1 = 1 + r1
    g2 = 1 + r2
    gs = (g1 + g2) / 2
    phase1 = ipow(g1, n)
    phase2 = ipow(g2, n)
    smooth_phase = ipow(gs, n)

    init_actual = c0 * phase1 * phase2
    init_smooth = c0 * smooth_phase * smooth_phase
    bound_actual = c1 * phase2
    bound_smooth = c1 * smooth_phase

    drag = init_smooth - init_actual
    uplift = bound_actual - bound_smooth
    total = c0 + c1
    final = (drag / total) * (uplift / total) * 100
    return {
        "final": final,
        "slots": {
            "first_phase_growth_checkpoint": phase1,
            "smoothed_phase_growth_checkpoint": smooth_phase,
        },
        "info": {"drag": drag, "uplift": uplift, "contributed": total},
    }

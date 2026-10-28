"""H021 (decimal, dimensionless): Hamada relevered beta from two comparables.

The reading, clause by clause:
* Hamada factor for a firm = [E + (1 - t) * D] / E.
* Each comparable's unlevered beta = observed levered beta / its factor.
* Unweighted arithmetic mean of the two unlevered betas.
* Target levered beta = mean * target factor [E_T + (1 - t_T) * D_T] / E_T.
* Debt beta zero; no other adjustment.
Slots: "tax-adjusted debt term used in its Hamada factor" with unit usd is the
(1 - t) * D term inside the bracket, for comparable A and comparable B.
"""
from hlib import num

KEY = "H021"


def solve(b):
    beta_a, d_a, e_a, t_a = num(
        b, "Comparable A has levered beta {N}, debt market value {N} USD, common-equity market value {N} USD, "
        "and marginal corporate tax rate {N}.")
    beta_b, d_b, e_b, t_b = num(b, "Comparable B has corresponding values {N}, {N} USD, {N} USD, and {N}.")
    d_t, e_t, t_t = num(b, "The target has debt market value {N} USD, common-equity market value {N} USD, and tax rate {N}.")
    adj_a = (1 - t_a) * d_a
    adj_b = (1 - t_b) * d_b
    fac_a = (e_a + adj_a) / e_a
    fac_b = (e_b + adj_b) / e_b
    fac_t = (e_t + (1 - t_t) * d_t) / e_t
    bu_a = beta_a / fac_a
    bu_b = beta_b / fac_b
    mean_bu = (bu_a + bu_b) / 2
    return {
        "final": mean_bu * fac_t,
        "slots": {
            "comparable_a_tax_adjusted_debt_checkpoint": adj_a,
            "comparable_b_tax_adjusted_debt_checkpoint": adj_b,
        },
        "info": {"unlevered_a": bu_a, "unlevered_b": bu_b, "mean_unlevered": mean_bu, "target_factor": fac_t},
    }

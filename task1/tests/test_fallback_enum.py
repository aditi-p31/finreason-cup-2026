# SPDX-License-Identifier: Apache-2.0
"""The residual-arm-avoiding blind guess for unseen enum templates.

An enum question states its own decision list, and the last arm of that list is
the residual one ("otherwise ...", "... when neither qualifies", or an option
the body never names).  Measured on the labelled corpus, gold lands on the
residual arm *less* often than chance, so the blind guess for a template we
have never seen must not pick it.  These tests pin the detector's behaviour on
the question shapes it has to read, pin the two properties that keep the guess
submission-safe -- it always returns a member of ``allowed_values`` and it is
deterministic -- and re-measure the prior against gold so the claim behind the
policy cannot go stale.
"""

from __future__ import annotations

import collections

import pytest

from finreason_solver.dataio import labelled_instances
from finreason_solver.fallback import blind_enum_guess, residual_branch


# -- detector behaviour -------------------------------------------------
@pytest.mark.parametrize(
    "text, allowed, expected",
    [
        # "otherwise <label>" -- the seen corpus's decision-list wording.
        (
            "Return high_risk when composite risk is at least 8; otherwise "
            "medium_risk when composite is at least 5; otherwise low_risk.",
            ["high_risk", "low_risk", "medium_risk"],
            "low_risk",
        ),
        # "<label> ... when neither qualifies" -- label before the cue.
        (
            "Choose the lower-cost feasible structure, prefer structure_a on a "
            "cost tie, or return no_feasible_structure when neither qualifies.",
            ["no_feasible_structure", "structure_a", "structure_b"],
            "no_feasible_structure",
        ),
        # "<label> otherwise" -- two-way pass/fail.
        (
            "Return within_budget when the capped loss does not exceed the "
            "budget and budget_breach otherwise.",
            ["budget_breach", "within_budget"],
            "budget_breach",
        ),
        # A label the body never names at all is the unspoken residual arm.
        (
            "Prefer the earlier date whenever it is feasible; otherwise choose "
            "the later date if feasible.",
            ["earlier_date", "later_date", "neither_date"],
            "neither_date",
        ),
        # No residual arm stated: nothing is disfavoured.
        (
            "Return low_risk for a total at most 5, medium_risk for a total "
            "from 6 through 8, and high_risk for a total of at least 9.",
            ["high_risk", "low_risk", "medium_risk"],
            None,
        ),
    ],
)
def test_residual_branch_reads_the_stated_decision_list(text, allowed, expected):
    assert residual_branch(text, sorted(allowed)) == expected


def test_detector_ignores_the_answer_format_footer():
    """The footer lists every label; reading it would defeat the unnamed rule."""

    text = (
        "Prefer the earlier date whenever it is feasible; otherwise choose the "
        "later date if feasible.\n\nAnswer format: return exactly one of these "
        "case-sensitive tokens and no additional text: `earlier_date`, "
        "`later_date`, `neither_date`."
    )
    assert residual_branch(text, ["earlier_date", "later_date", "neither_date"]) == (
        "neither_date"
    )


# -- guess safety -------------------------------------------------------
def test_guess_never_picks_the_residual_arm():
    text = (
        "Select the qualifying plan with the lower exact ratio, use plan_a on "
        "an exact tie, and use neither_plan if neither qualifies."
    )
    allowed = ["neither_plan", "plan_a", "plan_b"]
    assert residual_branch(text, sorted(allowed)) == "neither_plan"
    assert blind_enum_guess(text, allowed) == "plan_a"


def test_guess_is_always_an_allowed_value_and_deterministic():
    """An out-of-vocabulary value is a *validation* error, not a wrong answer."""

    cases = [
        ("Otherwise return no_action.", ["file_sar", "manual_review", "no_action"]),
        ("Return Neither when neither qualifies.", ["Bond A", "Bond B", "Neither"]),
        ("No decision list at all.", ["alpha", "beta"]),
        ("Otherwise alpha. Otherwise beta.", ["alpha", "beta"]),
    ]
    for text, allowed in cases:
        first = blind_enum_guess(text, allowed)
        assert first in allowed
        assert first == blind_enum_guess(text, list(reversed(allowed)))


def test_guess_falls_back_when_every_arm_is_residual():
    text = "Otherwise alpha. Otherwise beta."
    assert blind_enum_guess(text, ["alpha", "beta"]) in {"alpha", "beta"}


def test_no_allowed_values_yields_no_guess():
    assert blind_enum_guess("anything", []) is None


# -- the measurement the policy rests on --------------------------------
def _labelled_enum_units():
    """Every labelled enum output (final or trace slot) with its gold values."""

    units = []
    for template_id, instances in labelled_instances().items():
        spec = instances[0].answer_spec
        if spec.get("type") == "enum" and len(spec.get("allowed_values") or []) >= 2:
            units.append(
                (
                    sorted(spec["allowed_values"]),
                    instances[0].question["question"],
                    [instance.final_text for instance in instances],
                    template_id,
                )
            )
        slots = instances[0].question["trace_spec"]["slots"]
        for position, slot in enumerate(slots):
            result_spec = slot["result_spec"]
            if result_spec.get("type") != "enum":
                continue
            if len(result_spec.get("allowed_values") or []) < 2:
                continue
            units.append(
                (
                    sorted(result_spec["allowed_values"]),
                    instances[0].question["question"],
                    [instance.slot_texts[position] for instance in instances],
                    template_id,
                )
            )
    return units


def test_residual_arm_is_under_represented_in_gold():
    """Re-measure the prior the policy is built on, against the gold files.

    Leave-one-template-out is satisfied by construction: the detector reads
    only the target question's own text and fits nothing from any split.
    """

    residual_hits = alternative_hits = total = 0
    fired = 0
    for allowed, text, golds, _template_id in _labelled_enum_units():
        residual = residual_branch(text, allowed)
        if residual is None:
            continue
        fired += 1
        alternative = blind_enum_guess(text, allowed)
        assert alternative != residual
        total += len(golds)
        residual_hits += sum(1 for gold in golds if gold == residual)
        alternative_hits += sum(1 for gold in golds if gold == alternative)

    assert fired >= 15, "detector coverage of the labelled corpus regressed"
    assert total >= 165
    # Measured 56/165 vs 83/165 on task1-v4; the assertion is the direction
    # plus a margin, so a detector change that reverses the effect fails here.
    assert residual_hits < alternative_hits
    assert (alternative_hits - residual_hits) / total >= 0.10


def test_detector_fires_on_the_labelled_multi_way_decision_lists():
    """Guard against a cue regex that silently stops matching."""

    fired = collections.Counter()
    for allowed, text, _golds, _template_id in _labelled_enum_units():
        if len(allowed) >= 3:
            fired[residual_branch(text, allowed) is not None] += 1
    assert fired[True] >= 6


# -- template enum prior survives the skeleton loops ---------------------
def test_template_enum_prior_survives_a_preceding_decimal_slot():
    """Regression: ``guess`` used to rebind ``prior`` as its skeleton-loop
    variable, so an enum slot or enum final processed after a decimal slot
    lost the template's majority label.  On the shipped artifacts the
    fallback is only consulted for unmatched (hidden) cases, which carry no
    template prior, so the predictions were unaffected."""

    from finreason_solver.fallback import FallbackSolver

    solver = FallbackSolver(
        {
            "slot_priors": [
                {"template_id": "other", "words": ["ownership", "percent"],
                 "formula": "#0 + #1", "operands": [0, 1]},
            ],
            "final_priors": [],
            "idf": {},
            "template_enum": {
                "t.enum": {"final": "yes", "slots": {"flag": "on"}},
            },
        }
    )
    question = {
        "question": "Owner A holds 10 percent and owner B holds 15 percent.",
        "answer_spec": {"type": "enum", "allowed_values": ["no", "yes"]},
        "trace_spec": {
            "slots": [
                {"slot_id": "total", "description": "total ownership percent",
                 "result_spec": {"type": "decimal",
                                 "rounding": {"mode": "exact"}}},
                {"slot_id": "flag", "description": "threshold met",
                 "result_spec": {"type": "enum", "allowed_values": ["off", "on"]}},
            ]
        },
    }
    guess = solver.guess(question, template_id="t.enum")
    assert guess["steps"]["total"] == "25"
    assert guess["steps"]["flag"] == "on"
    assert guess["final"] == "yes"
    # Excluding the template (leave-one-template-out) drops its prior.
    held_out = solver.guess(question, template_id="t.enum", exclude="t.enum")
    assert "flag" not in held_out["steps"]

# SPDX-License-Identifier: Apache-2.0
"""The 11-instance gate cannot tell a formula from a coincidence; these tests can.

On 101 of the 290 templates the 11 labelled draws carry an exact relation the
unlabelled draws do not (a weight that is always 1, a split factor that is
always 2, two rates that are always equal).  A program that uses the wrong side
of such a relation reproduces every gold value and passes the ship gate.  The
reference forms in :mod:`finreason_solver.refforms` are the question text
written down; these tests pin that

* every reference passes the same 11-instance gate as a searched program,
* the build, after stages 4 and 5, agrees with its reference on every
  unlabelled leaderboard and test draw -- the only draws that can tell the
  two apart,
* stage 5 replaces a gate-passing coincidence and never loses a component,
* the reference values on the draws that expose the Sep 5 defects equal the
  values worked out by hand from the question text.
"""

from __future__ import annotations

import copy
import json
import sys
from fractions import Fraction
from pathlib import Path

import pytest

from finreason_solver import build_solvers, config, dataio, genforms, refforms
from finreason_solver import expr as E
from finreason_solver.derive import TemplateSolver, contract_test, evaluate_solver

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import degeneracy_audit as audit  # noqa: E402

pytestmark = pytest.mark.skipif(
    not config.SOLVERS_JSON.exists() or not config.SHAPE_INDEX_JSON.exists(),
    reason="run `python -m finreason_solver all` first",
)

TEXT_ONLY = {"fp.finance_regulation.kyc.document_validity.basic.v1"}


@pytest.fixture(scope="module")
def groups() -> dict:
    return dataio.labelled_instances()


@pytest.fixture(scope="module")
def payloads() -> dict[str, dict]:
    return {item["template_id"]: item for item in json.loads(config.SOLVERS_JSON.read_text())}


@pytest.fixture(scope="module")
def unseen() -> dict:
    from finreason_solver.shapes import ShapeIndex

    return audit.unseen_draws(ShapeIndex.load())


@pytest.fixture(scope="module")
def integrated(payloads: dict) -> dict[str, dict]:
    by_id = copy.deepcopy(payloads)
    build_solvers.apply_generator_forms(by_id)
    build_solvers.apply_reference_forms(by_id)
    return by_id


def _form(template_id: str):
    return refforms.REFERENCES.get(template_id) or genforms.FORMS[template_id]


# --- the references themselves ----------------------------------------------


def test_references_cover_every_template(groups: dict) -> None:
    covered = set(refforms.REFERENCES) | set(genforms.FORMS)
    assert not set(refforms.REFERENCES) & set(genforms.FORMS)
    assert covered == set(groups) - TEXT_ONLY


def test_fix_registries_name_registered_forms() -> None:
    assert refforms.FIXES <= set(refforms.REFERENCES)
    assert refforms.GENFORM_FIXES <= set(genforms.FORMS)


@pytest.mark.parametrize("template_id", sorted(refforms.REFERENCES))
def test_reference_reproduces_all_eleven_gold_instances(
    template_id: str, payloads: dict, groups: dict
) -> None:
    incumbent = TemplateSolver.from_json(payloads[template_id])
    candidate, defined = refforms.reference_solver(
        refforms.REFERENCES[template_id], incumbent, groups[template_id]
    )
    report = contract_test(candidate, groups[template_id])
    n = report["n_instances"]
    assert n == 11
    for cid in defined:
        ok = report["final_ok"] if cid == "final" else report["slot_ok"][cid]
        assert ok == n, (template_id, cid, ok)


# --- the build after stages 4 and 5 -----------------------------------------


def test_integrated_build_agrees_with_every_reference_on_every_unseen_draw(
    integrated: dict, groups: dict, unseen: dict
) -> None:
    """The regression that matters: no shipped component is a coincidence."""

    disagreements = []
    checked = 0
    for template_id, payload in sorted(integrated.items()):
        if template_id in TEXT_ONLY or payload.get("error"):
            continue
        solver = TemplateSolver.from_json(payload)
        ref, passing, _ = audit.reference_solver(_form(template_id), solver, groups[template_id])
        trusted = set(audit.trusted_components(solver))
        for draw in unseen.get(template_id, []):
            ours = audit.outputs(solver, draw.params, draw.question)
            theirs = audit.outputs(ref, draw.params, draw.question)
            for cid in passing:
                if cid not in trusted:
                    continue
                checked += 1
                if not audit.same(ours.get(cid), theirs.get(cid), audit.spec_of(draw.question, cid)):
                    disagreements.append((template_id, cid, draw.case_id))
    assert checked > 2000
    assert disagreements == []


def test_stage5_keeps_every_template_shippable_and_is_idempotent(integrated: dict) -> None:
    assert all(build_solvers.is_shippable(p) for tid, p in integrated.items()
               if tid not in TEXT_ONLY)
    before = sum(1 for p in integrated.values() if build_solvers.is_shippable(p))
    again = copy.deepcopy(integrated)
    assert build_solvers.apply_reference_forms(again) == []
    assert sum(1 for p in again.values() if build_solvers.is_shippable(p)) == before


def test_stage5_never_loses_a_validated_component(payloads: dict, integrated: dict) -> None:
    for template_id, payload in payloads.items():
        new = integrated[template_id]
        old_report, new_report = payload.get("contract_test"), new.get("contract_test")
        if not old_report:
            continue
        assert new_report["final_ok"] >= old_report["final_ok"], template_id
        for slot_id, count in old_report["slot_ok"].items():
            assert new_report["slot_ok"][slot_id] >= count, (template_id, slot_id)


# The Sep 5 search programs for three templates, verbatim from the accepted
# build: each reproduces all 11 labelled instances and each is wrong.
DEGENERATE = {
    "fp.fintech.robo_advisors.tax_loss_savings.advanced.v1": (
        "tax_ratio_trace", ["/", ["c", "4", "1"], ["p", 3]], "t1_7fawa5p7z7jghc5a34uqe"),
    "fp.crypto_finance.defi.liquidity_pool_reward.intermediate.v1": (
        "final", ["*", ["p", 1], ["/", ["s", 1], ["c", "100", "1"]]], "t1_altmwpbg6lhpbq6me47d6"),
    "fp.mergers_and_acquisitions.deal_structure.earnout_with_bonus_calculation.intermediate.v1": (
        "trace_1", ["/", ["min", ["p", 2], ["p", 3]], ["c", "10", "1"]], "t1_7ylmp32ljndebmabzkdzm"),
}


def _with_component(payload: dict, cid: str, expression) -> dict:
    out = copy.deepcopy(payload)
    if cid == "final":
        out["final"]["expr"] = expression
    else:
        for slot in out["slots"]:
            if slot["slot_id"] == cid:
                slot["expr"] = expression
    return out


@pytest.mark.parametrize("template_id", sorted(DEGENERATE))
def test_gate_is_blind_to_the_coincidence_and_stage5_repairs_it(
    template_id: str, integrated: dict, groups: dict, unseen: dict
) -> None:
    cid, expression, case_id = DEGENERATE[template_id]
    instances = groups[template_id]
    bad = _with_component(integrated[template_id], cid, expression)
    bad_solver = TemplateSolver.from_json(bad)
    report = contract_test(bad_solver, instances)
    ok = report["final_ok"] if cid == "final" else report["slot_ok"][cid]
    assert ok == 11  # the gate cannot see it

    draw = next(d for d in unseen[template_id] if d.case_id == case_id)
    ref, _, _ = audit.reference_solver(_form(template_id), bad_solver, instances)
    want = audit.outputs(ref, draw.params, draw.question)[cid]
    got = audit.outputs(bad_solver, draw.params, draw.question)[cid]
    spec = audit.spec_of(draw.question, cid)
    assert not audit.same(got, want, spec)  # the unlabelled draw can

    bad["contract_test"] = report
    by_id = {template_id: bad}
    if template_id in genforms.FORMS:
        assert template_id in refforms.GENFORM_FIXES
    assert build_solvers.apply_reference_forms(by_id) == [template_id]
    fixed = TemplateSolver.from_json(by_id[template_id])
    assert audit.same(audit.outputs(fixed, draw.params, draw.question)[cid], want, spec)
    assert build_solvers.is_shippable(by_id[template_id]) == build_solvers.is_shippable(bad)


# --- hand-checked values on the draws that expose the Sep 5 defects ----------

# Each value below was worked out from the question text alone.
HAND = [
    # earn-out: prorated 9704000*137144000/98650000 exceeds the 9704000 cap;
    # excess 137144000 - 1.1*98650000 = 28629000, 7% = 2004030 > cap 1538700.
    ("fp.mergers_and_acquisitions.deal_structure.earnout_with_bonus_calculation.intermediate.v1",
     "t1_7ylmp32ljndebmabzkdzm", {"trace_1": "9704000", "trace_2": "1538700", "final": "50173900.00"}),
    # EPS with a 3-for-1 split: (7233332 - 33600*2.1*4) / (600000*3).
    ("fp.corporate_finance.eps.eps_pref_div_split_weighted.advanced.v1",
     "t1_lnj7viiagvzgmmg6nu5bw", {"trace_1": "282240", "trace_2": "1800000"}),
    # tax-loss savings: 21 * (116 - 112) * 19%.
    ("fp.fintech.robo_advisors.tax_loss_savings.advanced.v1",
     "t1_7fawa5p7z7jghc5a34uqe", {"trace_2": "84", "trace_3": "0.19", "final": "15.96"}),
    # bridge fee 98.5%: 975 * 0.015 + 1 = 15.625.
    ("fp.crypto_finance.transaction_analysis.cross_chain_transfer.intermediate.v1",
     "t1_ptx4rxydrmmuio32tnck6", {"final": "15.63"}),
    # 0.02 USD cap over 3 units = 0.00667.
    ("fp.crypto_finance.tokenomics.token_price_calculation.basic.v1",
     "t1_apozht27hj6x5ywxr2tu6", {"final": "0.01"}),
    # 2428*0.4 = 971.2; credit min(293, 242.8) = 242.8; net 728.4.
    ("fp.personal_finance.taxcalc.foreign_tax_relief.advanced.v1",
     "t1_6f4winf5i42macoamvhvc", {"final": "728.40"}),
    # larger weight 0.599 is below 0.6: no penalty, base 5.
    ("fp.personal_finance.personalinvest.diversification_risk.advanced.v1",
     "t1_ihbajbf6gbargpucsgksk", {"concentration_condition": "false", "final": "5.00"}),
    # override is true, so high_risk regardless of composite 4.2.
    ("fp.finance_regulation.compliance.composite_risk.advanced.v1",
     "t1_urmjqybosob7dspwtszek", {"high_trigger": "true", "final": "high_risk"}),
    # 14.999 + 10.001 + 0 = 25.000 meets the 25 aggregate threshold.
    ("fp.finance_regulation.aml.multi_entity_ownership.intermediate.v1",
     "t1_qyju6t6slypb27uuytu3y", {"trace_1": "25", "final": "true"}),
    # total 11 < 12, but amount 100000 >= 100000 with low traceability.
    ("fp.finance_regulation.kyc.source_of_funds.intermediate.v1",
     "t1_j25avpy4es26msaecb332", {"final": "high_risk"}),
]


@pytest.mark.parametrize("template_id,case_id,expected", HAND)
def test_reference_matches_hand_worked_value(
    template_id: str, case_id: str, expected: dict, integrated: dict, groups: dict, unseen: dict
) -> None:
    draw = next(d for d in unseen[template_id] if d.case_id == case_id)
    solver = TemplateSolver.from_json(integrated[template_id])
    got = audit.outputs(solver, draw.params, draw.question)
    for cid, want in expected.items():
        key = cid
        if cid.startswith("trace_") and cid not in got:
            key = solver.slots[int(cid.split("_")[1]) - 1].slot_id
        assert audit.same(got[key], want, audit.spec_of(draw.question, key)), (cid, got[key], want)


# --- the audit machinery on synthetic columns -------------------------------


def _cols(*rows):
    return [tuple(Fraction(v) for v in col) for col in zip(*rows)]


def test_relation_scan_finds_each_kind_and_solves_back() -> None:
    rows = [(10, 5, 7, 3, 20, 1, 4), (20, 10, 17, 3, 40, 2, 6),
            (30, 15, 27, 3, 60, 3, 8), (50, 25, 47, 3, 100, 7, 9)]
    cols = _cols(*rows)
    found = {(r.kind, r.params) for r in audit.scan_relations(cols)}
    assert ("const", (3,)) in found            # p3 = 3
    assert ("prop", (0, 1)) in found           # p0 = 2 p1
    assert ("diff", (0, 2)) in found           # p0 = p2 + 3, exact on these rows
    assert ("affine", (1, 2)) in found         # p1 = (p2 + 3) / 2
    for rel in audit.scan_relations(cols):
        for index in rel.params:
            replacement = rel.solve_for(index)
            for row in rows:
                params = [Fraction(v) for v in row]
                params[index] = E.evaluate(replacement, params)
                assert rel.holds(params), (rel.text(), index)


def test_relation_scan_finds_an_arithmetic_progression() -> None:
    rows = [(1, 4, 7, 9), (2, 7, 12, 1), (5, 6, 7, 4), (0, 10, 20, 2), (3, 3, 3, 8)]
    kinds = {(r.kind, r.params, r.coef) for r in audit.scan_relations(_cols(*rows))}
    assert ("add3", (0, 1, 2), (Fraction(1), Fraction(-2), Fraction(1))) in kinds


def test_earnout_constants_hold_on_labelled_draws_and_break_only_on_test(
    groups: dict, unseen: dict
) -> None:
    template_id = "fp.mergers_and_acquisitions.deal_structure.earnout_with_bonus_calculation.intermediate.v1"
    relations = audit.audit_relations({template_id: groups[template_id]}, unseen)[template_id]
    broken = {row["relation"].text(): {b["case_id"] for b in row["broken"]}
              for row in relations["relations"] if row["broken"]}
    assert broken["p1 = 10000000"] == {"t1_7ylmp32ljndebmabzkdzm", "t1_ukb5wlmuzwxpuzeikdhks"}


def test_reference_parser_round_trips() -> None:
    params = [Fraction(v) for v in (0, 9704000, 98650000, 137144000)]
    assert E.evaluate(refforms.X("min(p1, p1*p3/p2)"), params) == Fraction(9704000)
    assert E.evaluate(refforms.X("-p1 + 0.105*p2 - 2**2"), params) == Fraction(-9704000) + Fraction(21, 200) * 98650000 - 4
    atoms, mode = refforms.condition("p1 >= p2 or p3 > 0")
    assert mode == "or" and [c for _, c in atoms] == [">=", ">"]

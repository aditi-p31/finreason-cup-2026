# SPDX-License-Identifier: Apache-2.0
"""Derive, contract-test and persist one solver per template."""

from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from . import config, expr as E
from .dataio import labelled_instances
from .derive import TemplateSolver, contract_test, derive_template

_GROUPS: dict[str, list] = {}


def _init() -> None:
    global _GROUPS
    if not _GROUPS:
        _GROUPS = labelled_instances()


def _one(job: tuple[str, int, bool, bool]) -> dict[str, Any]:
    template_id, depth, wide, stage3 = job
    _init()
    instances = _GROUPS[template_id]
    started = time.time()
    try:
        solver = derive_template(
            template_id, instances, depth=depth, wide=wide, stage3=stage3
        )
    except Exception as error:  # pragma: no cover - defensive
        return {
            "template_id": template_id,
            "error": f"{type(error).__name__}: {error}",
            "seconds": time.time() - started,
        }
    report = contract_test(solver, instances)
    # Ship each component on its own evidence: a template whose final answer we
    # could not derive still contributes its validated checkpoints, and those
    # are half the ranking score.
    solver.trusted_slots = tuple(
        slot_id
        for slot_id, count in report["slot_ok"].items()
        if count == report["n_instances"]
    )
    solver.trusted_final = bool(report["final_perfect"])
    payload = solver.to_json()
    payload["contract_test"] = report
    payload["seconds"] = round(time.time() - started, 3)
    print(
        f"[{'stage3' if stage3 else ('wide' if wide else 'base')}] {template_id} "
        f"final={report['final_ok']}/{report['n_instances']} "
        f"slots={sum(1 for c in report['slot_ok'].values() if c == report['n_instances'])}"
        f"/{report['n_slots']} {payload['seconds']}s",
        file=sys.stderr,
        flush=True,
    )
    payload["text"] = {
        "final": _describe_final(solver),
        "slots": {slot.slot_id: _describe_slot(slot) for slot in solver.slots},
    }
    return payload


def _describe_decision(decision) -> str:
    parts = []
    for atoms, mode, label in decision.rules:
        tests = f" {mode} ".join(
            f"{E.to_text(expression)} {comparator} 0"
            for expression, comparator in atoms
        )
        parts.append(f"if {tests} -> {label}")
    parts.append(f"else -> {decision.default}")
    return "; ".join(parts)


def _describe_slot(slot) -> str | None:
    if slot.kind == "enum":
        return _describe_decision(slot.decision) if slot.decision else None
    return E.to_text(slot.expression) if slot.expression else None


def _describe_final(solver) -> str | None:
    if solver.final_kind == "enum":
        return (
            _describe_decision(solver.final_decision)
            if solver.final_decision
            else None
        )
    return E.to_text(solver.final_expression) if solver.final_expression else None


def build(
    template_ids: list[str] | None = None,
    *,
    depth: int = 2,
    wide: bool = False,
    stage3: bool = False,
    workers: int | None = None,
) -> list[dict[str, Any]]:
    _init()
    ids = template_ids if template_ids is not None else sorted(_GROUPS)
    jobs = [(template_id, depth, wide, stage3) for template_id in ids]
    workers = workers or max(1, (os.cpu_count() or 2) - 1)
    if workers == 1:
        return [_one(job) for job in jobs]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_one, jobs, chunksize=1))


def build_two_stage(
    *, depth: int = 2, workers: int | None = None
) -> list[dict[str, Any]]:
    """Escalating passes: cheap, then wide, then the stage-3 machinery.

    Stage 2 adds one multiplicative level to the candidate pool.  It costs
    roughly twenty times as much per template, so it is spent only where the
    cheap pass failed to reproduce all 11 gold instances.  Stage 3 (transforms,
    sum peeling, piecewise conditionals, OR/AND decision rules over a deeper
    pool) costs more again and is spent only on what stage 2 still missed.
    """

    first = build(depth=depth, workers=workers)
    by_id = {payload["template_id"]: payload for payload in first}

    def escalate(retry: list[str], stage: int, **kwargs: Any) -> None:
        results = build(retry, depth=depth, workers=workers, **kwargs)
        for payload in results:
            previous = by_id[payload["template_id"]]
            if is_shippable(payload) or _better(payload, previous):
                payload["stage"] = stage
                by_id[payload["template_id"]] = payload

    retry = sorted(
        template_id
        for template_id, payload in by_id.items()
        if not is_shippable(payload)
    )
    if retry:
        escalate(retry, 2, wide=True)
    retry = sorted(
        template_id
        for template_id, payload in by_id.items()
        if not is_shippable(payload)
    )
    if retry:
        # Stage-3 pools are the largest; five workers keeps the build inside
        # 16 GB with headroom.
        stage3_workers = min(workers or max(1, (os.cpu_count() or 2) - 1), 5)
        results = build(retry, depth=depth, workers=stage3_workers, stage3=True)
        for payload in results:
            previous = by_id[payload["template_id"]]
            merged = _merge_components(previous, payload)
            best = previous
            for candidate, stage in ((payload, 3), (merged, 3)):
                if candidate is None:
                    continue
                if is_shippable(candidate) or _better(candidate, best):
                    candidate["stage"] = stage
                    best = candidate
            by_id[payload["template_id"]] = best
    apply_generator_forms(by_id)
    apply_reference_forms(by_id)
    for payload in by_id.values():
        payload.setdefault("stage", 1)
    return sorted(by_id.values(), key=lambda item: item["template_id"])


def apply_generator_forms(by_id: dict[str, dict[str, Any]]) -> list[str]:
    """Stage 4: the closed forms read off the published FinChain generators.

    Spent only on templates the search still could not close, and gated exactly
    like every other candidate: the recovered form is replayed against all 11
    gold instances and ships whole when every component reproduces, otherwise
    only the components that do are spliced into the incumbent's gaps.  A form
    that misreads its generator changes nothing.
    """

    from . import genforms

    _init()
    applied: list[str] = []
    for template_id, form in genforms.FORMS.items():
        payload = by_id.get(template_id)
        if payload is None or payload.get("error") or is_shippable(payload):
            continue
        instances = _GROUPS.get(template_id)
        if not instances:
            continue
        incumbent = TemplateSolver.from_json(payload)
        candidate = genforms.candidate_solver(form, incumbent, instances)
        report = contract_test(candidate, instances)
        proposal = _finish(candidate, report, payload)
        chosen = proposal
        if not is_shippable(proposal):
            # The whole form did not reproduce; keep only the components that
            # did, spliced into whatever the incumbent had not validated.
            merged = _merge_components(payload, proposal)
            chosen = merged if merged is not None else payload
        if chosen is payload or not _better(chosen, payload):
            continue
        chosen["stage"] = 4
        chosen["generator_form"] = {"source": form.source, "note": form.note}
        by_id[template_id] = chosen
        applied.append(template_id)
    return applied


def _component_texts(solver: TemplateSolver) -> dict[str, str | None]:
    texts = {slot.slot_id: _describe_slot(slot) for slot in solver.slots}
    texts["final"] = _describe_final(solver)
    return texts


def apply_reference_forms(by_id: dict[str, dict[str, Any]]) -> list[str]:
    """Stage 5: replace search programs the degeneracy audit found wrong.

    The 11-instance gate cannot tell a formula from a proportionality that
    holds on every labelled draw of its template (a weight that is always 1,
    a split factor that is always 2), and the search breaks the tie toward the
    *smallest* expression, which is exactly the coincidental one.  For the
    templates in :data:`refforms.FIXES` (reference forms read off the question
    text) and :data:`refforms.GENFORM_FIXES` (generator forms), every
    component the form defines that reproduces all 11 gold instances replaces
    the incumbent's, whether or not the incumbent also passed: the gate cannot
    rank two programs that both clear it, so the one read from the source
    wins.  A component whose reference fails the gate keeps the incumbent, so
    this pass never loses a validated component.  ``scripts/degeneracy_audit.py``
    is the evidence for membership in both registries.
    """

    from . import genforms, refforms

    _init()
    applied: list[str] = []
    for template_id in sorted(refforms.FIXES | refforms.GENFORM_FIXES):
        payload = by_id.get(template_id)
        instances = _GROUPS.get(template_id)
        if payload is None or payload.get("error") or not instances:
            continue
        form = refforms.REFERENCES.get(template_id) or genforms.FORMS.get(template_id)
        if form is None:
            continue
        incumbent = TemplateSolver.from_json(payload)
        candidate, defined = refforms.reference_solver(form, incumbent, instances)
        report = contract_test(candidate, instances)
        n = report["n_instances"]
        passing = {
            cid
            for cid in defined
            if (report["final_perfect"] if cid == "final" else report["slot_ok"].get(cid, 0) == n)
        }
        merged = TemplateSolver.from_json(payload)
        for position, slot in enumerate(candidate.slots):
            if slot.slot_id in passing:
                merged.slots[position] = slot
        if "final" in passing:
            merged.final_kind = candidate.final_kind
            merged.final_expression = candidate.final_expression
            merged.final_places = candidate.final_places
            merged.final_decision = candidate.final_decision
        before, after = _component_texts(incumbent), _component_texts(merged)
        replaced = {cid: before.get(cid) for cid in after if after[cid] != before.get(cid)}
        if not replaced:
            continue
        merged.source = "reference-form"
        chosen = _finish(merged, contract_test(merged, instances), payload)
        if _score_of(chosen) < _score_of(payload):
            continue
        chosen["stage"] = 5
        chosen["reference_form"] = {
            "source": getattr(form, "source", "question text"),
            "note": form.note,
            "replaced": replaced,
        }
        by_id[template_id] = chosen
        applied.append(template_id)
    return applied


def _finish(
    solver: TemplateSolver, report: dict[str, Any], previous: dict[str, Any]
) -> dict[str, Any]:
    """Serialise a contract-tested solver with its per-component trust marks."""

    solver.trusted_slots = tuple(
        slot_id
        for slot_id, count in report["slot_ok"].items()
        if count == report["n_instances"]
    )
    solver.trusted_final = bool(report["final_perfect"])
    payload = solver.to_json()
    payload["contract_test"] = report
    payload["seconds"] = previous.get("seconds")
    payload["text"] = {
        "final": _describe_final(solver),
        "slots": {slot.slot_id: _describe_slot(slot) for slot in solver.slots},
    }
    return payload


def _merge_components(
    first: dict[str, Any], second: dict[str, Any]
) -> dict[str, Any] | None:
    """Component-wise best of two derivations of the same template.

    The per-component ship gate makes this sound: a spliced slot or final is
    only ever *used* if the merged solver reproduces all 11 gold instances for
    that component in the fresh contract test run here, so a component whose
    prerequisites did not survive the merge simply fails its replay and is
    never trusted.
    """

    from .derive import TemplateSolver

    if first.get("error") or second.get("error"):
        return None
    report_a = first.get("contract_test")
    report_b = second.get("contract_test")
    if not report_a or not report_b:
        return None
    n = report_a["n_instances"]
    base_payload, other_payload = (
        (first, second) if _score_of(first) >= _score_of(second) else (second, first)
    )
    base = TemplateSolver.from_json(base_payload)
    other = TemplateSolver.from_json(other_payload)
    base_report = base_payload["contract_test"]
    other_report = other_payload["contract_test"]
    changed = False
    for position, slot in enumerate(base.slots):
        if position >= len(other.slots):
            break
        slot_id = slot.slot_id
        if (
            base_report["slot_ok"].get(slot_id, 0) < n
            and other_report["slot_ok"].get(slot_id, 0) == n
        ):
            base.slots[position] = other.slots[position]
            changed = True
    if not base_report["final_perfect"] and other_report["final_perfect"]:
        base.final_kind = other.final_kind
        base.final_expression = other.final_expression
        base.final_places = other.final_places
        base.final_decision = other.final_decision
        changed = True
    if not changed:
        return None
    _init()
    instances = _GROUPS[base.template_id]
    report = contract_test(base, instances)
    base.trusted_slots = tuple(
        slot_id
        for slot_id, count in report["slot_ok"].items()
        if count == report["n_instances"]
    )
    base.trusted_final = bool(report["final_perfect"])
    merged = base.to_json()
    merged["contract_test"] = report
    merged["seconds"] = round(
        (base_payload.get("seconds") or 0) + (other_payload.get("seconds") or 0), 3
    )
    merged["merged"] = True
    merged["text"] = {
        "final": _describe_final(base),
        "slots": {slot.slot_id: _describe_slot(slot) for slot in base.slots},
    }
    return merged


def _score_of(payload: dict[str, Any]) -> tuple[int, int]:
    report = payload.get("contract_test")
    if not report:
        return (-1, -1)
    return (
        report["final_ok"],
        sum(report["slot_ok"].values()),
    )


def _better(candidate: dict[str, Any], incumbent: dict[str, Any]) -> bool:
    return _score_of(candidate) > _score_of(incumbent)


def is_shippable(payload: dict[str, Any]) -> bool:
    """A solver ships only if it reproduces every gold value on every instance."""

    report = payload.get("contract_test")
    if not report:
        return False
    return bool(report["final_perfect"]) and bool(report["slots_perfect"])


def save(payloads: list[dict[str, Any]], path: Path | None = None) -> Path:
    path = path or config.SOLVERS_JSON
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(payloads, key=lambda item: item["template_id"])
    path.write_text(json.dumps(ordered, indent=1, sort_keys=True))
    return path


def load(path: Path | None = None) -> dict[str, TemplateSolver]:
    """Load every solver, each carrying the components that passed the gate."""

    path = path or config.SOLVERS_JSON
    payloads = json.loads(path.read_text())
    return {
        payload["template_id"]: TemplateSolver.from_json(payload)
        for payload in payloads
        if not payload.get("error")
        and (payload.get("trusted_slots") or payload.get("trusted_final"))
    }

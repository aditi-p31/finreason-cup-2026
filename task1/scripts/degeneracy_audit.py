#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Degeneracy audit: collinear labelled draws, and the solvers that lean on them.

The ship gate accepts a component when it reproduces all 11 labelled instances
of its template.  That gate cannot tell a formula from a *proportionality*: if
two parameters keep a fixed ratio (or difference, or one stays constant) across
every labelled draw, an expression that uses the wrong one reproduces every
gold value exactly and ships.  The held-out rebuild cannot see it either,
because the dev draw is one more labelled draw sharing the same correlation.

Only draws where the correlation *breaks* can expose it, and the only such
draws are the unlabelled leaderboard and test questions.  This script:

1. scans every template's labelled parameter vectors for exact relations --
   constant parameters, fixed ratios, fixed differences, affine pairs, and
   +/-1 additive or multiplicative triples -- and classifies each relation as
   *structural* (it also holds on every unseen draw of the template) or
   *labelled-only* (some unseen draw breaks it), per split;
2. marks every shipped component whose parameter closure touches a
   labelled-only relation (*exposed*), and substitutes the relation into the
   solver to see whether the component's emitted value would change on the
   draws that break it (*ambiguous*: the 11-instance gate cannot have chosen
   between the two readings);
3. compares every component against the reference form read off the public
   FinChain generator and the question text (``genforms.FORMS`` plus
   ``refforms.REFERENCES``) on every unseen draw -- a trusted component that
   passes the gate but disagrees with its reference is *degenerate*;
4. counts, in a submission archive, the emitted values that disagree with the
   reference, split by whether they came from a gate-trusted component (a
   degeneracy error) or from the fallback guess (not one).

No gold exists for the unseen draws, so no score is computed here: values are
compared to the reference with the organisers' own ``value_matches``.

The release does not ship ``test_submission.zip``; ``$W/test_submission.zip``
below is the archive built in REPRODUCE.md step 4 (``package --split test``).
A predictions.jsonl from step 3 works as ``--archive`` too.

    PYTHONPATH=src .venv/bin/python scripts/degeneracy_audit.py \\
        --build shipped=artifacts/solvers.json --with-fixes \\
        --archive test="$W/test_submission.zip"
"""

from __future__ import annotations

import argparse
import collections
import copy
import hashlib
import json
import sys
import zipfile
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from finreason_solver import config, dataio, expr as E  # noqa: E402

if str(config.CUP_REPO) not in sys.path:
    sys.path.insert(0, str(config.CUP_REPO))

from finreason_solver.derive import TemplateSolver, contract_test, evaluate_solver  # noqa: E402
from finreason_solver.numbers import extract_numbers  # noqa: E402
from finreason_solver.shapes import ShapeIndex  # noqa: E402
from finreason_task1.scoring import value_matches  # noqa: E402

FINAL = "final"


# --------------------------------------------------------------------------
# relations over a template's parameter columns
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Relation:
    """An exact identity among one to three parameters.

    ``kind`` is one of ``const`` (p_a = c), ``prop`` (p_a = r p_b),
    ``diff`` (p_a = p_b + d), ``affine`` (p_a = r p_b + d), ``add3``
    (s_a p_a + s_b p_b + s_c p_c = 0, signs +/-1) and ``mul3``
    (p_a^e_a p_b^e_b p_c^e_c = K, exponents +/-1).
    """

    kind: str
    params: tuple[int, ...]
    coef: tuple[Fraction, ...]

    def holds(self, p: Sequence[Fraction]) -> bool:
        try:
            if self.kind == "const":
                return p[self.params[0]] == self.coef[0]
            if self.kind in ("prop", "diff", "affine"):
                a, b = self.params
                r, d = self.coef
                return p[a] == r * p[b] + d
            if self.kind == "add3":
                return sum(s * p[i] for s, i in zip(self.coef, self.params)) == 0
            if self.kind == "mul3":
                *exps, k = self.coef
                value = Fraction(1)
                for e, i in zip(exps, self.params):
                    if p[i] == 0:
                        return False
                    value *= p[i] if e > 0 else 1 / p[i]
                return value == k
        except IndexError:
            return False
        raise ValueError(self.kind)

    def text(self) -> str:
        if self.kind == "const":
            return f"p{self.params[0]} = {self.coef[0]}"
        if self.kind in ("prop", "diff", "affine"):
            a, b = self.params
            r, d = self.coef
            rhs = f"p{b}" if r == 1 else f"{r}*p{b}"
            if d:
                rhs += f" + {d}" if d > 0 else f" - {-d}"
            return f"p{a} = {rhs}"
        if self.kind == "add3":
            terms = " ".join(
                f"{'+' if s > 0 else '-'} p{i}" for s, i in zip(self.coef, self.params)
            )
            return f"{terms.lstrip('+ ')} = 0"
        *exps, k = self.coef
        terms = " * ".join(
            f"p{i}" if e > 0 else f"(1/p{i})" for e, i in zip(exps, self.params)
        )
        return f"{terms} = {k}"

    def solve_for(self, index: int) -> list[Any]:
        """Expression for parameter ``index`` in terms of the others."""

        C = E.const
        P = E.param
        if self.kind == "const":
            return C(self.coef[0])
        if self.kind in ("prop", "diff", "affine"):
            a, b = self.params
            r, d = self.coef
            if index == a:
                return ["+", ["*", C(r), P(b)], C(d)]
            return ["/", ["-", P(a), C(d)], C(r)]
        if self.kind == "add3":
            signs = dict(zip(self.params, self.coef))
            # s_i p_i = -sum_{j != i} s_j p_j  ->  p_i = -(1/s_i) sum ...
            rest = [j for j in self.params if j != index]
            expr: list[Any] = ["*", C(-signs[rest[0]] / signs[index]), P(rest[0])]
            for j in rest[1:]:
                expr = ["+", expr, ["*", C(-signs[j] / signs[index]), P(j)]]
            return expr
        *exps, k = self.coef
        power = dict(zip(self.params, exps))
        rest = [j for j in self.params if j != index]
        # p_i^e_i = K / prod_{j} p_j^e_j
        other: list[Any] = C(k)
        for j in rest:
            other = ["/", other, P(j)] if power[j] > 0 else ["*", other, P(j)]
        return other if power[index] > 0 else ["/", C(Fraction(1)), other]


def _columns(instances) -> list[tuple[Fraction, ...]]:
    k = len(instances[0].params)
    return [tuple(inst.params[j] for inst in instances) for j in range(k)]


def scan_relations(cols: Sequence[Sequence[Fraction]]) -> list[Relation]:
    """Every exact relation of the supported kinds holding on all draws."""

    k = len(cols)
    n = len(cols[0]) if cols else 0
    found: list[Relation] = []
    constant = [len(set(col)) == 1 for col in cols]
    for a in range(k):
        if constant[a]:
            found.append(Relation("const", (a,), (cols[a][0],)))
    live = [j for j in range(k) if not constant[j]]
    related: set[frozenset[int]] = set()
    for a, b in combinations(live, 2):
        xs, ys = cols[b], cols[a]
        pivot = next((t for t in range(1, n) if xs[t] != xs[0]), None)
        if pivot is None:
            continue
        r = (ys[pivot] - ys[0]) / (xs[pivot] - xs[0])
        d = ys[0] - r * xs[0]
        if r == 0 or any(ys[t] != r * xs[t] + d for t in range(n)):
            continue
        kind = "prop" if d == 0 else ("diff" if r == 1 else "affine")
        found.append(Relation(kind, (a, b), (r, d)))
        related.add(frozenset((a, b)))
    for triple in combinations(live, 3):
        if any(frozenset(pair) in related for pair in combinations(triple, 2)):
            continue
        a, b, c = triple
        # +/-1 covers sums and differences; +/-2 and +/-1/2 cover arithmetic
        # progressions (p_a - 2 p_b + p_c = 0), which the labelled draws of
        # some templates follow exactly.
        weights = (Fraction(1), Fraction(-1), Fraction(2), Fraction(-2),
                   Fraction(1, 2), Fraction(-1, 2))
        for sb in weights:
            for sc in weights:
                if all(cols[a][t] + sb * cols[b][t] + sc * cols[c][t] == 0 for t in range(n)):
                    found.append(Relation("add3", triple, (Fraction(1), sb, sc)))
        if any(cols[j][t] == 0 for j in triple for t in range(n)):
            continue
        for eb in (1, -1):
            for ec in (1, -1):
                first = cols[a][0] * cols[b][0] ** eb * cols[c][0] ** ec
                if all(
                    cols[a][t] * cols[b][t] ** eb * cols[c][t] ** ec == first
                    for t in range(1, n)
                ):
                    found.append(
                        Relation(
                            "mul3", triple, (Fraction(1), Fraction(eb), Fraction(ec), first)
                        )
                    )
    return found


# --------------------------------------------------------------------------
# solver structure
# --------------------------------------------------------------------------


def _refs(expression, params: set[int], slots: set[int]) -> None:
    if expression is None:
        return
    head = expression[0]
    if head == "p":
        params.add(expression[1])
    elif head == "s":
        slots.add(expression[1])
    elif head == "c":
        return
    else:
        for child in expression[1:]:
            _refs(child, params, slots)


def _component_exprs(solver: TemplateSolver) -> dict[str, list[Any]]:
    out: dict[str, list[Any]] = {}
    for slot in solver.slots:
        exprs = []
        if slot.expression is not None:
            exprs.append(slot.expression)
        if slot.decision is not None:
            exprs.extend(e for atoms, _, _ in slot.decision.rules for e, _ in atoms)
        out[slot.slot_id] = exprs
    exprs = []
    if solver.final_expression is not None:
        exprs.append(solver.final_expression)
    if solver.final_decision is not None:
        exprs.extend(e for atoms, _, _ in solver.final_decision.rules for e, _ in atoms)
    out[FINAL] = exprs
    return out


def param_closure(solver: TemplateSolver) -> dict[str, set[int]]:
    """Parameters each component depends on, through the slots it reads."""

    direct: dict[str, tuple[set[int], set[int]]] = {}
    for cid, exprs in _component_exprs(solver).items():
        ps: set[int] = set()
        ss: set[int] = set()
        for e in exprs:
            _refs(e, ps, ss)
        direct[cid] = (ps, ss)
    slot_ids = [slot.slot_id for slot in solver.slots]
    closed: dict[str, set[int]] = {}

    def close(cid: str, seen: frozenset[str] = frozenset()) -> set[int]:
        if cid in closed:
            return closed[cid]
        ps, ss = direct[cid]
        out = set(ps)
        for s in ss:
            if s < len(slot_ids) and slot_ids[s] not in seen:
                out |= close(slot_ids[s], seen | {cid})
        closed[cid] = out
        return out

    for cid in direct:
        close(cid)
    return closed


def _substitute(expression, index: int, replacement):
    if expression is None:
        return None
    head = expression[0]
    if head == "p":
        return copy.deepcopy(replacement) if expression[1] == index else expression
    if head in ("c", "s"):
        return expression
    return [head, *(_substitute(child, index, replacement) for child in expression[1:])]


def substituted(solver: TemplateSolver, index: int, replacement) -> TemplateSolver:
    alt = copy.deepcopy(solver)
    for slot in alt.slots:
        slot.expression = _substitute(slot.expression, index, replacement)
        if slot.decision is not None:
            slot.decision.rules = [
                ([(_substitute(e, index, replacement), cmp) for e, cmp in atoms], mode, label)
                for atoms, mode, label in slot.decision.rules
            ]
    alt.final_expression = _substitute(alt.final_expression, index, replacement)
    if alt.final_decision is not None:
        alt.final_decision.rules = [
            ([(_substitute(e, index, replacement), cmp) for e, cmp in atoms], mode, label)
            for atoms, mode, label in alt.final_decision.rules
        ]
    return alt


# --------------------------------------------------------------------------
# inactive branches: the inequality analogue of a collinear parameter
# --------------------------------------------------------------------------

BRANCHING = ("min", "max", "ifgt", "ifge", "abs")


def _branch_nodes(expression, path: tuple[int, ...] = ()):
    if expression is None or expression[0] in ("c", "p", "s"):
        return
    if expression[0] in BRANCHING:
        yield path, expression
    for i, child in enumerate(expression[1:], start=1):
        yield from _branch_nodes(child, path + (i,))


def _at(expression, path):
    for i in path:
        expression = expression[i]
    return expression


def _replace_at(expression, path, new):
    if not path:
        return new
    out = list(expression)
    out[path[0]] = _replace_at(expression[path[0]], path[1:], new)
    return out


def _taken(node, params, slots) -> str | None:
    """Which branch ``node`` takes; ``None`` on a tie or an unevaluable input."""

    try:
        head = node[0]
        if head in ("min", "max"):
            left = E.evaluate(node[1], params, slots)
            right = E.evaluate(node[2], params, slots)
            if left == right:
                return None
            return "left" if (left < right) == (head == "min") else "right"
        if head in ("ifgt", "ifge"):
            cond = E.evaluate(node[1], params, slots)
            return "then" if (cond > 0 if head == "ifgt" else cond >= 0) else "else"
        value = E.evaluate(node[1], params, slots)
        return None if value == 0 else ("pos" if value > 0 else "neg")
    except (E.Unevaluable, ZeroDivisionError, OverflowError, ValueError):
        return None


def _fixed(node, branch: str):
    head = node[0]
    if head in ("min", "max"):
        return node[1] if branch == "left" else node[2]
    if head in ("ifgt", "ifge"):
        return node[2] if branch == "then" else node[3]
    return node[1] if branch == "pos" else ["neg", node[1]]


def thread_values(solver: TemplateSolver, params, question) -> list[Fraction] | None:
    """Slot values exactly as :func:`evaluate_solver` threads them forward."""

    from finreason_solver.numbers import gold_fraction

    values: list[Fraction] = []
    text_slots: dict[str, str] = {}
    if solver.text_rules is not None and question is not None:
        from finreason_solver import textrules

        _, text_slots = textrules.run(solver.text_rules, question)
    for slot in solver.slots:
        try:
            if slot.kind == "unsolved":
                text = text_slots.get(slot.slot_id)
                values.append(gold_fraction(text) if text is not None else Fraction(0))
            elif slot.kind == "enum":
                label = slot.decision.evaluate(params, values) if slot.decision else None
                if label is None:
                    return None
                values.append(Fraction(1) if label == "true" else Fraction(0))
            else:
                values.append(E.evaluate(slot.expression, params, values))
        except (E.Unevaluable, ZeroDivisionError, OverflowError, ValueError, ArithmeticError):
            return None
    return values


def inactive_branches(solver: TemplateSolver, instances) -> list[tuple[str, tuple[int, ...], str]]:
    """(component, node path, branch) for every branch node that never switches.

    Only numeric slot and final expressions are scanned.  A node that takes
    the same branch on every labelled draw is interchangeable, on those draws,
    with that branch alone -- ``max(x, 1)`` with ``x``, ``min(p0, 2)`` with
    ``2`` -- so the gate cannot have chosen between the two.
    """

    threaded = [thread_values(solver, inst.params, inst.question) for inst in instances]
    out = []
    components = [(s.slot_id, s.expression, pos) for pos, s in enumerate(solver.slots)
                  if s.kind in ("exact", "half_up") and s.expression is not None]
    if solver.final_expression is not None:
        components.append((FINAL, solver.final_expression, len(solver.slots)))
    for cid, expression, upto in components:
        for path, node in _branch_nodes(expression):
            seen = set()
            for inst, values in zip(instances, threaded):
                if values is None:
                    continue
                branch = _taken(node, inst.params, values[:upto])
                if branch is not None:
                    seen.add(branch)
            if len(seen) == 1:
                out.append((cid, path, seen.pop()))
    return out


def with_branch_fixed(solver: TemplateSolver, cid: str, path, branch: str) -> TemplateSolver:
    alt = copy.deepcopy(solver)
    if cid == FINAL:
        alt.final_expression = _replace_at(alt.final_expression, path,
                                           _fixed(_at(alt.final_expression, path), branch))
    else:
        for slot in alt.slots:
            if slot.slot_id == cid:
                slot.expression = _replace_at(slot.expression, path,
                                              _fixed(_at(slot.expression, path), branch))
    return alt


def trusted_components(solver: TemplateSolver) -> list[str]:
    out = [s for s in solver.trusted_slots]
    if solver.trusted_final:
        out.append(FINAL)
    return out


def outputs(solver: TemplateSolver, params, question) -> dict[str, str | None]:
    final, slots = evaluate_solver(solver, params, question)
    out: dict[str, str | None] = dict(slots)
    out[FINAL] = final
    return out


def spec_of(question: dict[str, Any], cid: str) -> dict[str, Any]:
    if cid == FINAL:
        return question["answer_spec"]
    for slot in question["trace_spec"]["slots"]:
        if slot["slot_id"] == cid:
            return slot["result_spec"]
    raise KeyError(cid)


def same(a: str | None, b: str | None, spec) -> bool:
    if a is None or b is None:
        return a is None and b is None
    try:
        return value_matches(a, b, spec)
    except Exception:  # an unparseable value is never a match
        return False


# --------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Draw:
    split: str
    case_id: str
    params: tuple[Fraction, ...]
    question: dict[str, Any]


def unseen_draws(index: ShapeIndex) -> dict[str, list[Draw]]:
    grouped: dict[str, list[Draw]] = collections.defaultdict(list)
    for name, loader in (("leaderboard", dataio.load_leaderboard), ("test", dataio.load_test)):
        split = loader()
        matches = index.identify_many(split.questions.values())
        for case_id in sorted(split.questions):
            template_id = matches[case_id].template_id
            if template_id:
                question = split.questions[case_id]
                grouped[template_id].append(
                    Draw(name, case_id, tuple(extract_numbers(question["question"])), question)
                )
    return grouped


def load_build(path: Path) -> dict[str, dict[str, Any]]:
    return {item["template_id"]: item for item in json.loads(path.read_text())}


def solvers_of(payloads: dict[str, dict[str, Any]]) -> dict[str, TemplateSolver]:
    return {
        tid: TemplateSolver.from_json(p) for tid, p in payloads.items() if not p.get("error")
    }


def with_fixes(payloads: dict[str, dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict]:
    """The build as the integration pass leaves it: stage 4 then stage 5."""

    from finreason_solver import build_solvers

    by_id = copy.deepcopy(payloads)
    applied4 = build_solvers.apply_generator_forms(by_id)
    applied5 = []
    if hasattr(build_solvers, "apply_reference_forms"):
        applied5 = build_solvers.apply_reference_forms(by_id)
    return by_id, {"stage4_generator_forms": applied4, "stage5_reference_forms": applied5}


def references() -> dict[str, Any]:
    from finreason_solver import genforms

    refs: dict[str, Any] = dict(genforms.FORMS)
    try:
        from finreason_solver import refforms
    except ImportError:
        return refs
    for tid, form in refforms.REFERENCES.items():
        if tid in refs:
            raise ValueError(f"{tid} registered twice")
        refs[tid] = form
    return refs


def reference_solver(form, incumbent: TemplateSolver, instances) -> tuple[TemplateSolver, list[str], dict]:
    """The reference program and the components it defines that pass the gate.

    ``report["reference_gate_failures"]`` lists defined components that do
    *not* reproduce all labelled instances: a misread reference, never used
    as a verdict.
    """

    from finreason_solver import refforms

    candidate, defined = refforms.reference_solver(form, incumbent, instances)
    report = contract_test(candidate, instances)
    n = report["n_instances"]
    passing = [
        cid
        for cid in defined
        if (report["final_perfect"] if cid == FINAL else report["slot_ok"].get(cid, 0) == n)
    ]
    report["reference_gate_failures"] = [cid for cid in defined if cid not in passing]
    return candidate, passing, report


# --------------------------------------------------------------------------
# the audit
# --------------------------------------------------------------------------


def audit_relations(groups, unseen) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for tid, instances in groups.items():
        cols = _columns(instances)
        relations = scan_relations(cols)
        rows = []
        for rel in relations:
            broken = [
                {"split": d.split, "case_id": d.case_id}
                for d in unseen.get(tid, [])
                if not rel.holds(d.params)
            ]
            rows.append({"relation": rel, "broken": broken})
        out[tid] = {"n_params": len(cols), "n_labelled": len(instances), "relations": rows}
    return out


def labelled_only(template_relations: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in template_relations["relations"] if row["broken"]]


def audit_build(
    label: str,
    payloads: dict[str, dict[str, Any]],
    groups,
    unseen,
    relations,
    refs,
) -> dict[str, Any]:
    solvers = solvers_of(payloads)
    exposed_rows = []
    ambiguous_rows = []
    branch_rows = []
    reference_rows = []
    gate_failures = []
    for tid in sorted(solvers):
        solver = solvers[tid]
        draws = unseen.get(tid, [])
        rel = relations.get(tid)
        if rel is None:
            continue
        lonly = labelled_only(rel)
        trusted = trusted_components(solver)
        closure = param_closure(solver)
        # (2) exposure and substitution ambiguity
        for row in lonly:
            relation: Relation = row["relation"]
            broken_ids = {b["case_id"] for b in row["broken"]}
            hit = [cid for cid in trusted if closure.get(cid, set()) & set(relation.params)]
            if not hit:
                continue
            exposed_rows.append(
                {"template_id": tid, "relation": relation.text(), "components": hit,
                 "broken_on": row["broken"]}
            )
            for q in relation.params:
                if not any(q in closure.get(cid, set()) for cid in hit):
                    continue
                alt = substituted(solver, q, relation.solve_for(q))
                changed = collections.Counter()
                for d in draws:
                    if d.case_id not in broken_ids:
                        continue
                    base = outputs(solver, d.params, d.question)
                    other = outputs(alt, d.params, d.question)
                    for cid in hit:
                        if not same(base.get(cid), other.get(cid), spec_of(d.question, cid)):
                            changed[cid] += 1
                for cid, count in sorted(changed.items()):
                    ambiguous_rows.append(
                        {"template_id": tid, "component": cid, "relation": relation.text(),
                         "substituted": f"p{q}", "draws_changed": count}
                    )
        # (2b) inactive branches: a clamp or conditional that never switches
        for cid, path, branch in inactive_branches(solver, groups[tid]):
            if cid not in trusted:
                continue
            alt = with_branch_fixed(solver, cid, path, branch)
            node = _at(solver.final_expression if cid == FINAL else
                       next(s.expression for s in solver.slots if s.slot_id == cid), path)
            changed = 0
            for d in draws:
                if not same(outputs(solver, d.params, d.question).get(cid),
                            outputs(alt, d.params, d.question).get(cid),
                            spec_of(d.question, cid)):
                    changed += 1
            branch_rows.append({"template_id": tid, "component": cid, "node": E.to_text(node),
                                "always": branch, "draws_changed": changed})
        # (3) reference agreement
        form = refs.get(tid)
        if form is None:
            continue
        ref, passing, report = reference_solver(form, solver, groups[tid])
        if report["reference_gate_failures"]:
            gate_failures.append({"template_id": tid, "components": report["reference_gate_failures"],
                                  "final_ok": report["final_ok"], "slot_ok": report["slot_ok"]})
        broken_any = {b["case_id"] for row in lonly for b in row["broken"]}
        for cid in passing:
            if cid not in trusted:
                continue
            disagree = []
            for d in draws:
                ours = outputs(solver, d.params, d.question).get(cid)
                theirs = outputs(ref, d.params, d.question).get(cid)
                if not same(ours, theirs, spec_of(d.question, cid)):
                    disagree.append(
                        {"split": d.split, "case_id": d.case_id, "emitted": ours,
                         "reference": theirs, "relation_broken": d.case_id in broken_any}
                    )
            reference_rows.append(
                {"template_id": tid, "component": cid, "unseen_draws": len(draws),
                 "disagreements": disagree}
            )
    degenerate = [r for r in reference_rows if r["disagreements"]]
    return {
        "label": label,
        "templates": len(solvers),
        "exposed": exposed_rows,
        "ambiguous": ambiguous_rows,
        "branch_flags": branch_rows,
        "reference_gate_failures": gate_failures,
        "reference_checks": reference_rows,
        "degenerate_components": [
            {"template_id": r["template_id"], "component": r["component"],
             "draws": len(r["disagreements"]),
             "unexplained": sum(1 for x in r["disagreements"] if not x["relation_broken"])}
            for r in degenerate
        ],
        "degenerate_templates": sorted({r["template_id"] for r in degenerate}),
    }


def read_archive(path: Path) -> dict[str, dict[str, Any]]:
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            text = archive.read("predictions.jsonl").decode("utf-8")
    else:
        text = path.read_text()
    rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    return {row["case_id"]: row for row in rows}


def audit_archive(
    label: str,
    path: Path,
    payloads: dict[str, dict[str, Any]],
    groups,
    unseen,
    refs,
) -> dict[str, Any]:
    predictions = read_archive(path)
    solvers = solvers_of(payloads)
    wrong: list[dict[str, Any]] = []
    checked = {"finals": 0, "slots": 0}
    for tid, form in sorted(refs.items()):
        solver = solvers.get(tid)
        if solver is None:
            continue
        ref, passing, _ = reference_solver(form, solver, groups[tid])
        trusted = set(trusted_components(solver))
        for d in unseen.get(tid, []):
            record = predictions.get(d.case_id)
            if record is None:
                continue
            theirs = outputs(ref, d.params, d.question)
            emitted = {s["slot_id"]: s["value"] for s in record["steps"]}
            emitted[FINAL] = (record.get("final_answer") or {}).get("value")
            for cid in passing:
                checked["finals" if cid == FINAL else "slots"] += 1
                value = emitted.get(cid)
                if same(value, theirs.get(cid), spec_of(d.question, cid)):
                    continue
                wrong.append(
                    {"template_id": tid, "split": d.split, "case_id": d.case_id,
                     "component": cid, "emitted": value, "reference": theirs.get(cid),
                     "cause": "gate-trusted component" if cid in trusted else
                              ("missing" if value is None else "fallback guess")}
                )
    def tally(cause: str) -> dict[str, int]:
        rows = [w for w in wrong if w["cause"] == cause]
        return {
            "finals": sum(1 for w in rows if w["component"] == FINAL),
            "slots": sum(1 for w in rows if w["component"] != FINAL),
            "cases": len({w["case_id"] for w in rows}),
            "templates": len({w["template_id"] for w in rows}),
        }
    return {
        "label": label,
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "records": len(predictions),
        "components_checked_against_reference": checked,
        "wrong_from_degenerate_trusted_components": tally("gate-trusted component"),
        "wrong_from_fallback_guesses": tally("fallback guess"),
        "rows": wrong,
    }


def cross_build(label_a, a, label_b, b, unseen) -> dict[str, Any]:
    """Components both builds trust, disagreeing on an unseen draw."""

    sa, sb = solvers_of(a), solvers_of(b)
    rows = []
    for tid in sorted(set(sa) & set(sb)):
        both = set(trusted_components(sa[tid])) & set(trusted_components(sb[tid]))
        if not both:
            continue
        for d in unseen.get(tid, []):
            oa = outputs(sa[tid], d.params, d.question)
            ob = outputs(sb[tid], d.params, d.question)
            for cid in sorted(both):
                if not same(oa.get(cid), ob.get(cid), spec_of(d.question, cid)):
                    rows.append({"template_id": tid, "component": cid, "split": d.split,
                                 "case_id": d.case_id, label_a: oa.get(cid), label_b: ob.get(cid)})
    return {
        "builds": [label_a, label_b],
        "disagreeing_components": len({(r["template_id"], r["component"]) for r in rows}),
        "disagreeing_templates": len({r["template_id"] for r in rows}),
        "rows": rows,
    }


def _jsonable(obj):
    if isinstance(obj, Relation):
        return obj.text()
    if isinstance(obj, Fraction):
        return str(obj)
    raise TypeError(type(obj))


def summarise_relations(relations, unseen) -> dict[str, Any]:
    kinds = collections.Counter()
    kinds_lonly = collections.Counter()
    templates_any = set()
    templates_nonconst = set()
    templates_lonly = set()
    templates_lonly_by_split = collections.defaultdict(set)
    breaks_by_split = collections.Counter()
    for tid, rel in relations.items():
        for row in rel["relations"]:
            r: Relation = row["relation"]
            kinds[r.kind] += 1
            templates_any.add(tid)
            if r.kind != "const":
                templates_nonconst.add(tid)
            if row["broken"]:
                kinds_lonly[r.kind] += 1
                templates_lonly.add(tid)
                for b in row["broken"]:
                    breaks_by_split[b["split"]] += 1
                    templates_lonly_by_split[b["split"]].add(tid)
    draws = collections.Counter(d.split for ds in unseen.values() for d in ds)
    return {
        "templates": len(relations),
        "unseen_draws_by_split": dict(draws),
        "relations_by_kind": dict(kinds),
        "labelled_only_relations_by_kind": dict(kinds_lonly),
        "templates_with_any_relation": len(templates_any),
        "templates_with_a_non_constant_relation": len(templates_nonconst),
        "templates_with_a_labelled_only_relation": len(templates_lonly),
        "templates_with_a_labelled_only_relation_by_split": {
            k: len(v) for k, v in sorted(templates_lonly_by_split.items())
        },
        "relation_breaks_by_split": dict(breaks_by_split),
        "labelled_only_templates": sorted(templates_lonly),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--build", action="append", default=[],
                        help="label=path to a solvers.json (repeatable)")
    parser.add_argument("--with-fixes", action="store_true",
                        help="also audit each build after the stage-4/5 integration pass, in memory")
    parser.add_argument("--archive", action="append", default=[],
                        help="label=path to a submission zip or predictions.jsonl, "
                             "checked against the FIRST --build")
    parser.add_argument("--cross", action="store_true", help="pairwise cross-build disagreement")
    parser.add_argument("--shape-index", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    builds = [tuple(b.split("=", 1)) for b in args.build] or [("shipped", str(config.SOLVERS_JSON))]
    index = ShapeIndex.load(Path(args.shape_index)) if args.shape_index else ShapeIndex.load()
    groups = dataio.labelled_instances()
    unseen = unseen_draws(index)
    relations = audit_relations(groups, unseen)
    refs = references()

    loaded = []
    for label, path in builds:
        payloads = load_build(Path(path))
        loaded.append((label, path, payloads, None))
        if args.with_fixes:
            fixed, applied = with_fixes(payloads)
            loaded.append((f"{label}+fixes", path, fixed, applied))

    report: dict[str, Any] = {
        "inputs": {
            "builds": {label: {"path": path, "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}
                       for label, path in builds},
            "references": len(refs),
            "labelled_templates": len(groups),
        },
        "benchmark_relations": summarise_relations(relations, unseen),
        "per_template_labelled_only_relations": {
            tid: [{"relation": row["relation"].text(), "kind": row["relation"].kind,
                   "broken_on": row["broken"]} for row in labelled_only(rel)]
            for tid, rel in relations.items() if labelled_only(rel)
        },
        "unreviewed_templates": sorted(
            tid for tid, rel in relations.items() if labelled_only(rel) and tid not in refs
        ),
        "builds": {},
        "archives": {},
    }
    for label, path, payloads, applied in loaded:
        result = audit_build(label, payloads, groups, unseen, relations, refs)
        if applied is not None:
            result["integration_applied"] = applied
        report["builds"][label] = result
    first_label, _, first_payloads, _ = loaded[0]
    for spec in args.archive:
        label, path = spec.split("=", 1)
        report["archives"][label] = audit_archive(label, Path(path), first_payloads, groups, unseen, refs)
    if args.cross and len(loaded) > 1:
        report["cross_build"] = [
            cross_build(la, pa, lb, pb, unseen)
            for (la, _, pa, _), (lb, _, pb, _) in combinations(loaded, 2)
        ]

    def recall(b: dict[str, Any]) -> dict[str, Any]:
        """How much of the reference-confirmed degeneracy each automatic screen sees."""

        deg = {(r["template_id"], r["component"]) for r in b["degenerate_components"]}
        screens = {
            "collinearity": {(r["template_id"], r["component"]) for r in b["ambiguous"]},
            "inactive_branch": {(r["template_id"], r["component"])
                                for r in b["branch_flags"] if r["draws_changed"]},
        }
        screens["either"] = screens["collinearity"] | screens["inactive_branch"]
        out = {}
        for name, hit in screens.items():
            out[name] = {
                "flagged_components": len(hit),
                "flagged_templates": len({t for t, _ in hit}),
                "degenerate_components_caught": len(deg & hit),
                "degenerate_templates_caught": len({t for t, _ in deg} & {t for t, _ in hit}),
            }
        out["degenerate_components"] = len(deg)
        out["degenerate_templates"] = len({t for t, _ in deg})
        return out

    brief = {
        "benchmark_relations": {k: v for k, v in report["benchmark_relations"].items()
                                if k != "labelled_only_templates"},
        "unreviewed_templates": len(report["unreviewed_templates"]),
        "builds": {
            label: {
                "exposed_components": len({(r["template_id"], c) for r in b["exposed"] for c in r["components"]}),
                "exposed_templates": len({r["template_id"] for r in b["exposed"]}),
                "ambiguous_components": len({(r["template_id"], r["component"]) for r in b["ambiguous"]}),
                "ambiguous_templates": len({r["template_id"] for r in b["ambiguous"]}),
                "reference_checked_components": len(b["reference_checks"]),
                "reference_checked_templates": len({r["template_id"] for r in b["reference_checks"]}),
                "reference_gate_failures": len(b["reference_gate_failures"]),
                "degenerate_components": len(b["degenerate_components"]),
                "degenerate_templates": len(b["degenerate_templates"]),
                "unexplained_disagreements": sum(x["unexplained"] for x in b["degenerate_components"]),
                "screen_recall": recall(b),
            }
            for label, b in report["builds"].items()
        },
        "archives": {
            label: {k: v for k, v in a.items() if k != "rows"} for label, a in report["archives"].items()
        },
    }
    report["summary"] = brief
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=1, sort_keys=True, default=_jsonable))
    print(json.dumps(brief, indent=1, sort_keys=True, default=_jsonable))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

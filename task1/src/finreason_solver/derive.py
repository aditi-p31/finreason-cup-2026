# SPDX-License-Identifier: Apache-2.0
"""Drive the induction search over every template and validate the result.

A solver is only recorded when it reproduces *all* gold values on *all* 11
labelled instances of its template: the final answer under the scorer's own
half-up canonicalisation and every trace slot under exact ``Fraction``
equality.  Anything short of that is reported as unsolved rather than shipped.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Mapping, Sequence

from . import config, expr as E
from .dataio import Instance, labelled_instances
from .induction import (
    Pool,
    Vector,
    build_pool,
    evaluate_vector,
    leaf_items_for,
    search_exact,
    search_rounded,
)
from .numbers import fraction_to_decimal, gold_fraction

COMPARATORS = (">", ">=", "<", "<=")

_ROUND_FAILED = object()


def _text_registry() -> dict[str, Any]:
    from . import textrules

    return textrules.REGISTRY


def _safe_round(value: Fraction, places: int):
    """``fraction_to_decimal`` that returns a sentinel instead of raising."""

    try:
        return fraction_to_decimal(value, places)
    except (ValueError, ArithmeticError):
        return _ROUND_FAILED


Atom = tuple[list[Any], str]  # (expression, comparator)


@dataclass
class DecisionList:
    """Sign-test rules, first match wins.

    A rule is one or two atoms ``expr <comparator> 0`` joined by ``or`` /
    ``and``: the cup's regulation questions state their precedence chains as
    exactly this shape ("file_sar when score is at least 8 *or* both flags are
    true").  Single-atom rules serialise in the original flat form.
    """

    rules: list[tuple[list[Atom], str, str]]  # (atoms, "or"|"and", label)
    default: str

    def to_json(self) -> dict[str, Any]:
        serialised = []
        for atoms, mode, label in self.rules:
            if len(atoms) == 1:
                expression, comparator = atoms[0]
                serialised.append(
                    {"expr": expression, "comparator": comparator, "label": label}
                )
            else:
                serialised.append(
                    {
                        "atoms": [
                            {"expr": expression, "comparator": comparator}
                            for expression, comparator in atoms
                        ],
                        "op": mode,
                        "label": label,
                    }
                )
        return {"rules": serialised, "default": self.default}

    @staticmethod
    def from_json(payload: dict[str, Any]) -> "DecisionList":
        rules: list[tuple[list[Atom], str, str]] = []
        for rule in payload["rules"]:
            if "atoms" in rule:
                atoms = [
                    (atom["expr"], atom["comparator"]) for atom in rule["atoms"]
                ]
                rules.append((atoms, rule["op"], rule["label"]))
            else:
                rules.append(
                    ([(rule["expr"], rule["comparator"])], "or", rule["label"])
                )
        return DecisionList(rules=rules, default=payload["default"])

    def evaluate(
        self, params: Sequence[Fraction], slots: Sequence[Fraction]
    ) -> str | None:
        for atoms, mode, label in self.rules:
            verdicts = []
            for expression, comparator in atoms:
                try:
                    value = E.evaluate(expression, params, slots)
                except (E.Unevaluable, ZeroDivisionError, OverflowError, ValueError):
                    return None
                verdicts.append(_holds(value, comparator))
            if any(verdicts) if mode == "or" else all(verdicts):
                return label
        return self.default


@dataclass
class SlotSolver:
    slot_id: str
    kind: str  # "exact" | "half_up" | "enum"
    expression: list[Any] | None = None
    places: int | None = None
    decision: DecisionList | None = None

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"slot_id": self.slot_id, "kind": self.kind}
        if self.expression is not None:
            payload["expr"] = self.expression
        if self.places is not None:
            payload["places"] = self.places
        if self.decision is not None:
            payload["decision"] = self.decision.to_json()
        return payload

    @staticmethod
    def from_json(payload: dict[str, Any]) -> "SlotSolver":
        decision = payload.get("decision")
        return SlotSolver(
            slot_id=payload["slot_id"],
            kind=payload["kind"],
            expression=payload.get("expr"),
            places=payload.get("places"),
            decision=DecisionList.from_json(decision) if decision else None,
        )


@dataclass
class TemplateSolver:
    template_id: str
    n_params: int
    slots: list[SlotSolver] = field(default_factory=list)
    final_kind: str = "decimal"
    final_expression: list[Any] | None = None
    final_places: int | None = None
    final_decision: DecisionList | None = None
    validation: dict[str, Any] = field(default_factory=dict)
    source: str = "induced"
    trusted_slots: tuple[str, ...] = ()
    trusted_final: bool = False
    text_rules: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "n_params": self.n_params,
            "source": self.source,
            "slots": [slot.to_json() for slot in self.slots],
            "final": {
                "kind": self.final_kind,
                "expr": self.final_expression,
                "places": self.final_places,
                "decision": (
                    self.final_decision.to_json() if self.final_decision else None
                ),
            },
            "validation": self.validation,
            "trusted_slots": list(self.trusted_slots),
            "trusted_final": self.trusted_final,
            "text_rules": self.text_rules,
        }

    @staticmethod
    def from_json(payload: dict[str, Any]) -> "TemplateSolver":
        final = payload["final"]
        decision = final.get("decision")
        return TemplateSolver(
            template_id=payload["template_id"],
            n_params=payload["n_params"],
            slots=[SlotSolver.from_json(item) for item in payload["slots"]],
            final_kind=final["kind"],
            final_expression=final.get("expr"),
            final_places=final.get("places"),
            final_decision=DecisionList.from_json(decision) if decision else None,
            validation=payload.get("validation", {}),
            source=payload.get("source", "induced"),
            trusted_slots=tuple(payload.get("trusted_slots", ())),
            trusted_final=bool(payload.get("trusted_final", False)),
            text_rules=payload.get("text_rules"),
        )


def _param_vectors(instances: Sequence[Instance]) -> list[Vector]:
    counts = {len(instance.params) for instance in instances}
    if len(counts) != 1:
        raise ValueError(f"inconsistent parameter counts {sorted(counts)}")
    n_params = counts.pop()
    return [
        tuple(instance.params[index] for instance in instances)
        for index in range(n_params)
    ]


def _make_verifier(param_vectors, slot_vectors, n):
    def verify(expression):
        return evaluate_vector(expression, param_vectors, slot_vectors, n)

    return verify


def _holds(value: Fraction, comparator: str) -> bool:
    if comparator == ">":
        return value > 0
    if comparator == ">=":
        return value >= 0
    if comparator == "<":
        return value < 0
    return value <= 0


def _sign_mask_index(pool: Pool, n: int) -> dict[str, dict[int, list[Any]]]:
    """For each comparator, distinct truth bitmasks over all ``n`` instances.

    One pass over the pool (sign of a Fraction is the sign of its numerator,
    so no Fraction comparisons happen) replaces what used to be a full-pool
    scan per candidate label per comparator per greedy round.  Per mask the
    smallest expression is kept, which matches the old scan's tie-break.
    """

    full = (1 << n) - 1
    index: dict[str, dict[int, list[Any]]] = {
        comparator: {} for comparator in COMPARATORS
    }
    sizes: dict[str, dict[int, int]] = {
        comparator: {} for comparator in COMPARATORS
    }
    for vector in pool.order:
        expression = pool.by_key[vector]
        size = E.size(expression)
        gt_mask = 0
        ge_mask = 0
        for position in range(n):
            numerator = vector[position].numerator
            if numerator > 0:
                gt_mask |= 1 << position
                ge_mask |= 1 << position
            elif numerator == 0:
                ge_mask |= 1 << position
        for comparator, mask in (
            (">", gt_mask),
            (">=", ge_mask),
            ("<", full & ~ge_mask),
            ("<=", full & ~gt_mask),
        ):
            store = sizes[comparator]
            previous = store.get(mask)
            if previous is None or size < previous:
                store[mask] = size
                index[comparator][mask] = expression
    return index


def _project_masks(
    index: dict[str, dict[int, list[Any]]], remaining: Sequence[int]
) -> dict[int, Atom]:
    """Restrict the full-instance mask index to the ``remaining`` positions."""

    projected: dict[int, Atom] = {}
    sizes: dict[int, int] = {}
    for comparator in COMPARATORS:
        for mask, expression in index[comparator].items():
            reduced = 0
            for position, instance in enumerate(remaining):
                if mask & (1 << instance):
                    reduced |= 1 << position
            size = E.size(expression)
            previous = sizes.get(reduced)
            if previous is None or size < previous:
                sizes[reduced] = size
                projected[reduced] = (expression, comparator)
    return projected


def _checked_atom(
    atom: Atom, wanted: int, remaining: Sequence[int], verify
) -> bool:
    """Recompute an atom from scratch and recheck its truth mask."""

    if verify is None:
        return True
    expression, comparator = atom
    recomputed = verify(expression)
    if recomputed is None:
        return False
    recheck = 0
    for position, instance in enumerate(remaining):
        if _holds(recomputed[instance], comparator):
            recheck |= 1 << position
    return recheck == wanted


def _pair_rule(
    masks: dict[int, Atom],
    wanted: int,
    full: int,
    remaining: Sequence[int],
    verify,
) -> tuple[list[Atom], str] | None:
    """Two verified atoms whose OR (or AND) hits exactly ``wanted``."""

    or_parts = [
        mask for mask in masks if mask and mask & ~wanted == 0
    ]
    for i, first in enumerate(or_parts):
        for second in or_parts[i:]:
            if first | second == wanted:
                if _checked_atom(
                    masks[first], first, remaining, verify
                ) and _checked_atom(masks[second], second, remaining, verify):
                    return [masks[first], masks[second]], "or"
    and_parts = [
        mask for mask in masks if mask != full and mask & wanted == wanted
    ]
    for i, first in enumerate(and_parts):
        for second in and_parts[i:]:
            if first & second == wanted:
                if _checked_atom(
                    masks[first], first, remaining, verify
                ) and _checked_atom(masks[second], second, remaining, verify):
                    return [masks[first], masks[second]], "and"
    return None


def _enum_search(
    pool: Pool,
    labels: Sequence[str],
    allowed: Sequence[str],
    verify=None,
) -> DecisionList | None:
    """Greedily peel one label at a time off with a sign test.

    Cup enum outputs are not all binary: risk bands and AML dispositions have
    three to five ordered outcomes, and the question states them as a
    precedence chain ("high_risk when ... otherwise medium_risk when ...").  A
    decision list is the same shape, so each round looks for one expression
    whose sign exactly separates one remaining label from the rest, and falls
    back to a disjunction or conjunction of two sign tests -- the "at least 8
    or the override flag is true" rules the regulation templates state.
    """

    remaining = list(range(len(labels)))
    rules: list[tuple[list[Atom], str, str]] = []
    guard = 0
    index = _sign_mask_index(pool, len(labels))
    while len({labels[i] for i in remaining}) > 1:
        guard += 1
        if guard > 8:
            return None
        progressed = False
        masks = _project_masks(index, remaining)
        full_mask = (1 << len(remaining)) - 1
        for candidate in sorted({labels[i] for i in remaining}):
            wanted_mask = sum(
                1 << position
                for position, i in enumerate(remaining)
                if labels[i] == candidate
            )
            atom = masks.get(wanted_mask)
            if atom is not None and _checked_atom(
                atom, wanted_mask, remaining, verify
            ):
                rules.append(([atom], "or", candidate))
                remaining = [i for i in remaining if labels[i] != candidate]
                progressed = True
                break
            # No single sign test separates this label; try two atoms.
            paired = _pair_rule(masks, wanted_mask, full_mask, remaining, verify)
            if paired is not None:
                atoms, mode = paired
                rules.append((atoms, mode, candidate))
                remaining = [i for i in remaining if labels[i] != candidate]
                progressed = True
                break
        if not progressed:
            return None
    if not remaining:
        return None
    default = labels[remaining[0]]
    if not rules and len(set(labels)) == 1:
        # Degenerate: every instance carries the same label.  Refuse rather
        # than ship a constant that has not actually been discriminated.
        return None
    return DecisionList(rules=rules, default=default)


def _is_boolean_enum(spec: Mapping[str, Any]) -> bool:
    return spec.get("type") == "enum" and set(
        spec.get("allowed_values") or []
    ) == {"false", "true"}


STAGE3_EXTRA_LEFT_MARKS = (
    ("wide_priority", 15_000),
    ("additive", 10_000),
    ("wide2", 10_000),
    ("minmax_leaf", 5_000),
    ("minmax_leaf2", 4_000),
    ("geometric", 2_000),
    ("powers", 5_000),
)


def _stage3_lefts(pool: Pool) -> list[Vector]:
    lefts: list[Vector] = []
    for name, cap in STAGE3_EXTRA_LEFT_MARKS:
        lefts.extend(pool.marked(name)[:cap])
    return lefts


def _stage3_solve_numeric(
    pool: Pool,
    param_vectors: Sequence[Vector],
    solved_slot_vectors: Sequence[Vector],
    n: int,
    verify,
    target: Vector,
    places: int | None,
) -> list[Any] | None:
    """Run the stage-3 searches on one numeric target."""

    from .stage3 import Stage3Search

    if places is None:
        intervals = [(value, value) for value in target]

        def check(vector: Vector) -> bool:
            return vector == target

    else:
        half = Fraction(1, 2 * 10**places)
        intervals = [(value - half, value + half) for value in target]
        expected = []
        for value in target:
            try:
                expected.append(fraction_to_decimal(value, places))
            except (ValueError, ArithmeticError):
                return None

        def check(vector: Vector) -> bool:
            for value, want in zip(vector, expected):
                try:
                    if fraction_to_decimal(value, places) != want:
                        return False
                except (ValueError, ArithmeticError):
                    return False
            return True

    search = Stage3Search(pool, param_vectors, solved_slot_vectors, n, verify)
    return search.solve(intervals, check)


def derive_template(
    template_id: str,
    instances: Sequence[Instance],
    *,
    depth: int = 2,
    wide: bool = False,
    stage3: bool = False,
) -> TemplateSolver:
    n = len(instances)
    param_vectors = _param_vectors(instances)
    first = instances[0]
    slot_specs = first.slot_specs
    slot_ids = list(first.slot_ids)
    answer_spec = first.answer_spec

    has_enum = answer_spec["type"] == "enum" or any(
        spec["type"] == "enum" for spec in slot_specs
    )
    solver = TemplateSolver(
        template_id=template_id, n_params=len(param_vectors)
    )
    if template_id in _text_registry():
        solver.text_rules = template_id
    solved_slot_vectors: list[Vector] = []
    unsolved_slots: list[str] = []

    def make_pool() -> Pool:
        return build_pool(
            param_vectors,
            solved_slot_vectors,
            n,
            depth=depth,
            wide=wide,
            stage3=stage3,
            minmax_pairs=has_enum,
        )

    for position, (slot_id, spec) in enumerate(zip(slot_ids, slot_specs)):
        pool = make_pool()
        verify = _make_verifier(param_vectors, solved_slot_vectors, n)
        texts = [instance.slot_texts[position] for instance in instances]
        if spec["type"] == "enum":
            decision = _enum_search(
                pool, texts, spec.get("allowed_values", []), verify
            )
            if decision is None:
                unsolved_slots.append(slot_id)
                solver.slots.append(SlotSolver(slot_id=slot_id, kind="unsolved"))
            else:
                solver.slots.append(
                    SlotSolver(slot_id=slot_id, kind="enum", decision=decision)
                )
            # A boolean enum slot *can* feed later arithmetic as its 1/0 truth
            # value ("add the penalty when the concentration condition holds"),
            # so a solved one threads its gold truth vector; the prediction
            # path threads the decision's own output, and the contract test
            # replays that end to end.  Anything else threads a zero so the
            # positional slot references of later slots stay aligned.
            if _is_boolean_enum(spec) and decision is not None:
                solved_slot_vectors.append(
                    tuple(
                        Fraction(1) if text == "true" else Fraction(0)
                        for text in texts
                    )
                )
            else:
                solved_slot_vectors.append(tuple(Fraction(0) for _ in range(n)))
            continue
        target = tuple(gold_fraction(text) for text in texts)
        rounding = spec.get("rounding") or {}
        places = (
            int(rounding["decimal_places"])
            if rounding.get("mode") == "half_up"
            else None
        )
        extra_lefts = _stage3_lefts(pool) if stage3 else ()
        expression = search_exact(pool, target, verify, extra_lefts=extra_lefts)
        if expression is None and places is not None:
            expression = search_rounded(
                pool,
                target,
                places,
                leaf_items_for(pool, param_vectors, solved_slot_vectors),
                verify,
                extra_lefts=extra_lefts,
            )
        if expression is None and stage3:
            expression = _stage3_solve_numeric(
                pool, param_vectors, solved_slot_vectors, n, verify, target, places
            )
        if expression is None:
            unsolved_slots.append(slot_id)
            solver.slots.append(SlotSolver(slot_id=slot_id, kind="unsolved"))
        elif places is not None:
            solver.slots.append(
                SlotSolver(
                    slot_id=slot_id,
                    kind="half_up",
                    expression=expression,
                    places=places,
                )
            )
        else:
            solver.slots.append(
                SlotSolver(slot_id=slot_id, kind="exact", expression=expression)
            )
        # A slot we could not derive still threads its gold vector on, so the
        # *later* slots stay derivable.  At prediction time it has no value, so
        # anything that genuinely depends on it fails its contract test and is
        # never trusted; anything that does not depend on it still ships.
        solved_slot_vectors.append(target)

    pool = make_pool()
    verify = _make_verifier(param_vectors, solved_slot_vectors, n)
    if answer_spec["type"] == "enum":
        labels = [instance.final_text or "" for instance in instances]
        decision = _enum_search(
            pool, labels, answer_spec.get("allowed_values", []), verify
        )
        solver.final_kind = "enum"
        solver.final_decision = decision
    else:
        rounding = answer_spec.get("rounding") or {}
        places = (
            int(rounding["decimal_places"])
            if rounding.get("mode") == "half_up"
            else None
        )
        target = tuple(
            gold_fraction(instance.final_text or "0") for instance in instances
        )
        extra_lefts = _stage3_lefts(pool) if stage3 else ()
        expression = search_exact(pool, target, verify, extra_lefts=extra_lefts)
        if expression is None and places is not None:
            expression = search_rounded(
                pool,
                target,
                places,
                leaf_items_for(pool, param_vectors, solved_slot_vectors),
                verify,
                extra_lefts=extra_lefts,
            )
        if expression is None and stage3:
            expression = _stage3_solve_numeric(
                pool, param_vectors, solved_slot_vectors, n, verify, target, places
            )
        solver.final_kind = "decimal" if places is not None else "exact"
        solver.final_expression = expression
        solver.final_places = places

    solver.validation = {
        "n_instances": n,
        "n_slots": len(slot_ids),
        "slots_solved": len(solver.slots),
        "unsolved_slots": unsolved_slots,
        "final_solved": (
            solver.final_decision is not None
            if solver.final_kind == "enum"
            else solver.final_expression is not None
        ),
        "depth": depth,
        "wide": wide,
        "stage3": stage3,
    }
    return solver


def evaluate_solver(
    solver: TemplateSolver,
    params: Sequence[Fraction],
    question: Mapping[str, Any] | None = None,
) -> tuple[str | None, dict[str, str]]:
    """Run a solver and return ``(final_value_text, {slot_id: text})``.

    Values are returned as *exact* payloads: the caller renders them under the
    question's own spec.  ``None`` means the solver could not produce a value.
    When the template has registered text rules, they fill exactly the
    components the induced program left unsolved, parsing the mapping stated in
    ``question`` itself.
    """

    from .numbers import render_exact

    text_final: str | None = None
    text_slots: dict[str, str] = {}
    if solver.text_rules is not None and question is not None:
        from . import textrules

        text_final, text_slots = textrules.run(solver.text_rules, question)

    slot_values: list[Fraction] = []
    outputs: dict[str, str] = {}
    for slot in solver.slots:
        if slot.kind == "unsolved":
            text_value = text_slots.get(slot.slot_id)
            threaded = Fraction(0)
            if text_value is not None:
                outputs[slot.slot_id] = text_value
                try:
                    threaded = gold_fraction(text_value)
                except (ValueError, ArithmeticError):
                    threaded = Fraction(0)
            slot_values.append(threaded)
            continue
        try:
            if slot.kind == "enum":
                assert slot.decision is not None
                label = slot.decision.evaluate(params, slot_values)
                if label is None:
                    break
                outputs[slot.slot_id] = label
                # A boolean verdict feeds later arithmetic as 1/0, mirroring
                # the gold-truth threading used during derivation.
                if label in ("true", "false"):
                    slot_values.append(
                        Fraction(1) if label == "true" else Fraction(0)
                    )
                else:
                    slot_values.append(Fraction(0))
                continue
            assert slot.expression is not None
            value = E.evaluate(slot.expression, params, slot_values)
        except (E.Unevaluable, ZeroDivisionError, OverflowError, ValueError):
            break
        slot_values.append(value)
        try:
            if slot.kind == "half_up" and slot.places is not None:
                outputs[slot.slot_id] = format(
                    fraction_to_decimal(value, slot.places), "f"
                )
            else:
                outputs[slot.slot_id] = render_exact(value)
        except (ValueError, ArithmeticError):
            break

    final_text: str | None = None
    if len(slot_values) != len(solver.slots):
        return None, outputs
    if solver.final_kind == "enum":
        if solver.final_decision is not None:
            final_text = solver.final_decision.evaluate(params, slot_values)
        if final_text is None:
            final_text = text_final
        return final_text, outputs
    if solver.final_expression is None and text_final is not None:
        return text_final, outputs
    if solver.final_expression is not None:
        try:
            value = E.evaluate(solver.final_expression, params, slot_values)
        except (E.Unevaluable, ZeroDivisionError, OverflowError, ValueError):
            value = None
        if value is not None:
            if solver.final_places is None:
                try:
                    final_text = render_exact(value)
                except ValueError:
                    final_text = None
            else:
                try:
                    final_text = format(
                        fraction_to_decimal(value, solver.final_places), "f"
                    )
                except (ValueError, ArithmeticError):
                    final_text = None
    return final_text, outputs


def contract_test(
    solver: TemplateSolver, instances: Sequence[Instance]
) -> dict[str, Any]:
    """Replay a solver against every gold instance of its template."""

    from .numbers import canonical_decimal

    final_ok = 0
    slot_ok = {slot_id: 0 for slot_id in instances[0].slot_ids}
    for instance in instances:
        final_text, slot_texts = evaluate_solver(
            solver, instance.params, instance.question
        )
        if final_text is not None and instance.final_text is not None:
            spec = instance.answer_spec
            if spec["type"] == "enum":
                if final_text == instance.final_text:
                    final_ok += 1
            elif (spec.get("rounding") or {}).get("mode") == "exact":
                if gold_fraction(final_text) == gold_fraction(instance.final_text):
                    final_ok += 1
            else:
                if canonical_decimal(final_text, spec) == canonical_decimal(
                    instance.final_text, spec
                ):
                    final_ok += 1
        for position, slot_id in enumerate(instance.slot_ids):
            produced = slot_texts.get(slot_id)
            if produced is None:
                continue
            spec = instance.slot_specs[position]
            gold_text = instance.slot_texts[position]
            if spec["type"] == "enum":
                if produced == gold_text:
                    slot_ok[slot_id] += 1
            elif (spec.get("rounding") or {}).get("mode") == "exact":
                if gold_fraction(produced) == gold_fraction(gold_text):
                    slot_ok[slot_id] += 1
            else:
                if canonical_decimal(produced, spec) == canonical_decimal(
                    gold_text, spec
                ):
                    slot_ok[slot_id] += 1
    n = len(instances)
    return {
        "n_instances": n,
        "final_ok": final_ok,
        "final_perfect": final_ok == n,
        "slot_ok": slot_ok,
        "slots_perfect": all(count == n for count in slot_ok.values()),
        "n_slots": len(slot_ok),
    }

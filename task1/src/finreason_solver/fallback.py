# SPDX-License-Identifier: Apache-2.0
"""Best-effort guesses for cases whose template we have never seen.

The 348 ``test_private_hidden`` cases are unseen template *structures*, so no
induced solver applies to them.  Because the scorer treats a wrong answer and a
``null`` identically (both score 0), a guess is strictly free upside, and this
module supplies one.

The prior is learned, deterministically, from the labelled corpus: every gold
slot in train+dev is paired with the smallest expression over that question's
own numbers that reproduces it, and the resulting (slot-description wording ->
expression skeleton) associations are reused by nearest-neighbour on the words
of the unseen slot description.  Its measured value is reported by
``scripts/evaluate_fallback.py`` under leave-one-template-out, and it is only
worth what that measurement says.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import config, expr as E
from .numbers import extract_numbers, fraction_to_decimal, render_exact

_WORD = re.compile(r"[a-z]+")
STOPWORDS = frozenset(
    "the a an of to in for and or as at by on is are be compute report "
    "value amount total this that with from result step".split()
)


def tokenise(text: str) -> list[str]:
    return [word for word in _WORD.findall(text.lower()) if word not in STOPWORDS]


# -- residual-branch detection ------------------------------------------
#
# An enum question states its own decision list, and the last arm of that list
# is the residual ("otherwise ...", "... when neither qualifies", or a label
# the body never names at all).  Measured on the labelled corpus, the residual
# arm is the gold answer *less* often than chance, so a blind guess should not
# land on it.  The detector reads only the target question's own text and fits
# nothing, so it is leave-one-template-out by construction.
_NONE_OF_THE_ABOVE = r"(?:when|if)\s+(?:neither|none|no\s+\w+\s+(?:qualifies|is))"
_NONE_BEFORE_LABEL = re.compile(_NONE_OF_THE_ABOVE + r"[^.;]{0,50}?$", re.I)
_NONE_AFTER_LABEL = re.compile(r"^[^.;]{0,50}?" + _NONE_OF_THE_ABOVE, re.I)
_ELSE_BEFORE_LABEL = re.compile(r"\b(otherwise|else)\b[^.;]{0,50}?$", re.I)
_ELSE_AFTER_LABEL = re.compile(r"^[^.;]{0,50}?\b(otherwise|else)\b", re.I)


def residual_branch(question_text: str, allowed: Sequence[str]) -> str | None:
    """The label this question's own decision list marks as its residual arm.

    Returns ``None`` when the text states no residual arm, in which case no
    label is disfavoured.
    """

    body = question_text.split("Answer format:")[0].lower()
    mentioned: dict[str, list[tuple[int, int]]] = {}
    for label in allowed:
        # Questions name an arm either as the literal token (``later_date``) or
        # as the prose it is built from (``the later date``), so underscores
        # and spaces are matched interchangeably.
        pattern = re.compile(
            r"[_ ]".join(re.escape(part) for part in re.split(r"[_ ]+", label.lower()))
        )
        spans = [(m.start(), m.end()) for m in pattern.finditer(body)]
        if spans:
            mentioned[label] = spans
    def last_label_near(before_cue: re.Pattern[str], after_cue: re.Pattern[str]):
        best: str | None = None
        best_position = -1
        for label, spans in mentioned.items():
            for start, end in spans:
                near_before = before_cue.search(body[max(0, start - 60) : start])
                near_after = after_cue.search(body[end : end + 60])
                if (near_before or near_after) and start > best_position:
                    best_position = start
                    best = label
        return best

    # Tier 1: an arm the text ties explicitly to "when neither / if none" is
    # the residual one whatever else the decision list says.
    explicit = last_label_near(_NONE_BEFORE_LABEL, _NONE_AFTER_LABEL)
    if explicit is not None:
        return explicit
    # Tier 2: every arm but one is named, so the unnamed arm is the case the
    # decision list never had to spell out.
    unnamed = [label for label in allowed if label not in mentioned]
    if len(unnamed) == 1 and len(mentioned) == len(allowed) - 1:
        return unnamed[0]
    # Tier 3: the last arm introduced by a plain "otherwise"/"else".
    return last_label_near(_ELSE_BEFORE_LABEL, _ELSE_AFTER_LABEL)


def blind_enum_guess(question_text: str, allowed: Sequence[str]) -> str | None:
    """Deterministic label to guess when no per-template prior applies."""

    ordered = sorted(allowed)
    if not ordered:
        return None
    residual = residual_branch(question_text, ordered)
    preferred = [label for label in ordered if label != residual]
    return (preferred or ordered)[0]


# Skeletons are small closed-form shapes over abstract operands, evaluated as
# plain lambdas (no ``eval``) so the fit stays fast enough to cross-validate.
def _safe(function):
    def wrapper(*operands: Fraction):
        try:
            return function(*operands)
        except (ZeroDivisionError, ArithmeticError, ValueError):
            return None

    return wrapper


SKELETONS: tuple[tuple[str, int, Any], ...] = (
    ("#0", 1, _safe(lambda a: a)),
    ("#0 - #1", 2, _safe(lambda a, b: a - b)),
    ("#0 + #1", 2, _safe(lambda a, b: a + b)),
    ("#0 * #1", 2, _safe(lambda a, b: a * b)),
    ("#0 / #1", 2, _safe(lambda a, b: a / b)),
    ("#0 * #1 / 100", 2, _safe(lambda a, b: a * b / 100)),
    ("#0 / #1 * 100", 2, _safe(lambda a, b: a / b * 100)),
    ("#0 * (1 - #1)", 2, _safe(lambda a, b: a * (1 - b))),
    ("#0 * (1 + #1)", 2, _safe(lambda a, b: a * (1 + b))),
    ("(#0 + #1) / 2", 2, _safe(lambda a, b: (a + b) / 2)),
    ("#0 * #1 * #2", 3, _safe(lambda a, b, c: a * b * c)),
    ("#0 + #1 + #2", 3, _safe(lambda a, b, c: a + b + c)),
    ("#0 - #1 - #2", 3, _safe(lambda a, b, c: a - b - c)),
    ("(#0 - #1) / #2", 3, _safe(lambda a, b, c: (a - b) / c)),
    ("(#0 - #1) * #2", 3, _safe(lambda a, b, c: (a - b) * c)),
)

SKELETON_BY_NAME = {name: function for name, _, function in SKELETONS}


def _eval_skeleton(formula: str, operands: Sequence[Fraction]) -> Fraction | None:
    function = SKELETON_BY_NAME.get(formula)
    if function is None:
        return None
    return function(*operands)


class FallbackSolver:
    """Description-conditioned nearest-neighbour guesser."""

    def __init__(self, model: dict[str, Any]) -> None:
        self.slot_priors: list[dict[str, Any]] = model.get("slot_priors", [])
        self.final_priors: list[dict[str, Any]] = model.get("final_priors", [])
        self.idf: dict[str, float] = model.get("idf", {})
        # Per-template majority label for enum outputs we could not derive a
        # rule for.  Guessing costs nothing under the cup scorer, and the
        # measured leave-one-out accuracy of this prior is in
        # artifacts/enum_prior_loo.json.
        self.template_enum: dict[str, Any] = model.get("template_enum", {})

    # -- persistence ----------------------------------------------------
    @classmethod
    def load(cls, path: Path | None = None) -> "FallbackSolver":
        path = path or (config.ARTIFACTS / "fallback_model.json")
        if not path.exists():
            return cls({})
        return cls(json.loads(path.read_text()))

    def save(self, path: Path | None = None) -> Path:
        path = path or (config.ARTIFACTS / "fallback_model.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "slot_priors": self.slot_priors,
                    "final_priors": self.final_priors,
                    "idf": self.idf,
                    "template_enum": self.template_enum,
                },
                indent=1,
                sort_keys=True,
            )
        )
        return path

    # -- inference ------------------------------------------------------
    def _similarity(self, left: Sequence[str], right: Sequence[str]) -> float:
        left_set, right_set = set(left), set(right)
        if not left_set or not right_set:
            return 0.0
        shared = left_set & right_set
        if not shared:
            return 0.0
        weight = sum(self.idf.get(word, 1.0) for word in shared)
        norm = math.sqrt(
            sum(self.idf.get(word, 1.0) for word in left_set)
            * sum(self.idf.get(word, 1.0) for word in right_set)
        )
        return weight / norm if norm else 0.0

    def _rank(
        self,
        priors: list[dict[str, Any]],
        words: Sequence[str],
        n_params: int,
        exclude: str | None = None,
    ) -> list[dict[str, Any]]:
        scored = []
        for prior in priors:
            if exclude is not None and prior["template_id"] == exclude:
                continue
            score = self._similarity(words, prior["words"])
            if score <= 0:
                continue
            scored.append((score, prior))
        scored.sort(key=lambda item: (-item[0], item[1]["formula"]))
        return [prior for _, prior in scored[:12]]

    def _value(
        self, prior: Mapping[str, Any], params: Sequence[Fraction]
    ) -> Fraction | None:
        indices = prior["operands"]
        if any(index >= len(params) for index in indices):
            return None
        return _eval_skeleton(prior["formula"], [params[index] for index in indices])

    def guess(
        self,
        question: Mapping[str, Any],
        exclude: str | None = None,
        template_id: str | None = None,
    ) -> dict[str, Any]:
        params = extract_numbers(question["question"])
        # The per-template enum prior.  Kept under its own name: the skeleton
        # loops below bind ``candidate``, so an enum slot or enum final that
        # comes after a decimal slot still reads this template's prior.
        template_prior = (
            self.template_enum.get(template_id, {})
            if template_id and template_id != exclude
            else {}
        )
        body = question["question"]
        if not params:
            final_label = template_prior.get("final")
            if final_label is None and question["answer_spec"].get("type") == "enum":
                final_label = blind_enum_guess(
                    body, question["answer_spec"].get("allowed_values") or []
                )
            return {"final": final_label, "steps": dict(template_prior.get("slots", {}))}
        steps: dict[str, str] = {}
        for slot in question["trace_spec"]["slots"]:
            spec = slot["result_spec"]
            if spec.get("type") != "decimal":
                label = (template_prior.get("slots") or {}).get(slot["slot_id"])
                if label is not None and label in (
                    spec.get("allowed_values") or []
                ):
                    steps[slot["slot_id"]] = label
                continue
            words = tokenise(slot["description"])
            for candidate in self._rank(
                self.slot_priors, words, len(params), exclude
            ):
                value = self._value(candidate, params)
                if value is None:
                    continue
                try:
                    if (spec.get("rounding") or {}).get("mode") == "exact":
                        steps[slot["slot_id"]] = render_exact(value)
                    else:
                        steps[slot["slot_id"]] = format(
                            fraction_to_decimal(
                                value, int(spec["rounding"]["decimal_places"])
                            ),
                            "f",
                        )
                except (ValueError, ArithmeticError):
                    continue
                break

        final: str | None = None
        answer_spec = question["answer_spec"]
        if answer_spec.get("type") == "decimal":
            words = tokenise(body[-400:])
            for candidate in self._rank(
                self.final_priors, words, len(params), exclude
            ):
                value = self._value(candidate, params)
                if value is None:
                    continue
                rounding = answer_spec.get("rounding") or {}
                try:
                    if rounding.get("mode") == "exact":
                        final = render_exact(value)
                    else:
                        final = format(
                            fraction_to_decimal(
                                value, int(rounding["decimal_places"])
                            ),
                            "f",
                        )
                except (ValueError, ArithmeticError):
                    continue
                break
        elif answer_spec.get("type") == "enum":
            allowed = answer_spec.get("allowed_values") or []
            label = template_prior.get("final")
            if label in allowed:
                final = label
            elif allowed:
                final = blind_enum_guess(body, allowed)
        return {"final": final, "steps": steps}


def fit(instances_by_template: Mapping[str, Sequence[Any]]) -> FallbackSolver:
    """Learn the description -> skeleton prior from labelled data."""

    slot_priors: list[dict[str, Any]] = []
    final_priors: list[dict[str, Any]] = []
    document_frequency: Counter[str] = Counter()
    documents = 0

    for template_id, instances in instances_by_template.items():
        first = instances[0]
        n_params = len(first.params)
        indices = range(min(n_params, 8))
        for position, slot in enumerate(first.question["trace_spec"]["slots"]):
            spec = slot["result_spec"]
            if spec.get("type") != "decimal":
                continue
            targets = [instance.slot_fraction(position) for instance in instances]
            hit = _best_skeleton(instances, targets, indices)
            if hit is None:
                continue
            formula, operands = hit
            words = tokenise(slot["description"])
            documents += 1
            document_frequency.update(set(words))
            slot_priors.append(
                {
                    "template_id": template_id,
                    "words": words,
                    "formula": formula,
                    "operands": list(operands),
                }
            )
        if first.answer_spec.get("type") == "decimal":
            targets = [instance.final_fraction for instance in instances]
            hit = _best_skeleton(instances, targets, indices)
            if hit is not None:
                formula, operands = hit
                words = tokenise(first.question["question"][-400:])
                documents += 1
                document_frequency.update(set(words))
                final_priors.append(
                    {
                        "template_id": template_id,
                        "words": words,
                        "formula": formula,
                        "operands": list(operands),
                    }
                )

    idf = {
        word: math.log((documents + 1) / (count + 1)) + 1.0
        for word, count in document_frequency.items()
    }
    return FallbackSolver(
        {
            "slot_priors": slot_priors,
            "final_priors": final_priors,
            "idf": idf,
            "template_enum": _enum_priors(instances_by_template),
        }
    )


def _majority(labels: Sequence[str]) -> str:
    counts = Counter(labels)
    return min(counts, key=lambda label: (-counts[label], label))


def _enum_priors(instances_by_template: Mapping[str, Sequence[Any]]) -> dict[str, Any]:
    priors: dict[str, Any] = {}
    for template_id, instances in instances_by_template.items():
        first = instances[0]
        entry: dict[str, Any] = {}
        if first.answer_spec.get("type") == "enum":
            entry["final"] = _majority(
                [instance.final_text or "" for instance in instances]
            )
        slots: dict[str, str] = {}
        for position, slot in enumerate(first.question["trace_spec"]["slots"]):
            if slot["result_spec"].get("type") != "enum":
                continue
            slots[slot["slot_id"]] = _majority(
                [instance.slot_texts[position] for instance in instances]
            )
        if slots:
            entry["slots"] = slots
        if entry:
            priors[template_id] = entry
    return priors


def _best_skeleton(instances, targets, indices):
    """Smallest skeleton + operand binding reproducing every gold value."""

    from itertools import permutations

    probe = instances[0]
    probe_target = targets[0]
    for formula, arity, function in SKELETONS:
        for binding in permutations(indices, arity):
            # Cheap filter on one instance before paying for all eleven.
            value = function(*[probe.params[index] for index in binding])
            if value is None or value != probe_target:
                continue
            if all(
                function(*[instance.params[index] for index in binding]) == target
                for instance, target in zip(instances[1:], targets[1:])
            ):
                return formula, binding
    return None

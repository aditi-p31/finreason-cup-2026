# SPDX-License-Identifier: Apache-2.0
"""Turn a question split into a contract-legal ``predictions.jsonl``.

Abstention policy (read off ``finreason_task1/scoring.py``, not guessed):
``score_case`` scores ``fac = int(final_answer is not None and value_matches(...))``
and counts a slot only when it is present *and* matches.  A wrong value and a
``null`` therefore score identically -- zero -- so there is never a reason to
abstain on accuracy grounds.  The only real risk is a value that fails
``validate_submission``, because an invalid record rejects the *whole*
submission.  So: always emit a guess when it serialises legally, and emit
``null`` only when it does not.
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import config
from .dataio import Split
from .derive import TemplateSolver, evaluate_solver
from .fallback import FallbackSolver
from .numbers import extract_numbers, gold_fraction, serialisable
from .shapes import Match, ShapeIndex


def _legal_value(text: str, spec: Mapping[str, Any]) -> bool:
    if spec.get("type") == "enum":
        return text in (spec.get("allowed_values") or [])
    try:
        value = gold_fraction(text)
    except (ValueError, ArithmeticError):
        return False
    return serialisable(value, spec)


def predict_case(
    question: Mapping[str, Any],
    solver: TemplateSolver | None,
    fallback: FallbackSolver | None = None,
    template_id: str | None = None,
    form_answer: Any | None = None,
) -> dict[str, Any]:
    params = extract_numbers(question["question"])
    final_text: str | None = None
    slot_texts: dict[str, str] = {}
    if solver is not None and len(params) == solver.n_params:
        final_text, slot_texts = evaluate_solver(solver, params, question)
        # Only components that reproduced every gold instance are used.
        if not solver.trusted_final:
            final_text = None
        slot_texts = {
            slot_id: value
            for slot_id, value in slot_texts.items()
            if slot_id in solver.trusted_slots
        }
    elif solver is None and form_answer is not None:
        # Optional route (``--hidden-forms``, off by default): the serialised
        # final and slots of an unmatched question's per-template form.  Slots
        # the form leaves out are filled by the fallback below.
        final_text = form_answer.final
        slot_texts = dict(form_answer.slots)
    if fallback is not None and (
        final_text is None
        or len(slot_texts) < len(question["trace_spec"]["slots"])
    ):
        guess = fallback.guess(question, template_id=template_id)
        if final_text is None:
            final_text = guess.get("final")
        for slot_id, value in guess.get("steps", {}).items():
            slot_texts.setdefault(slot_id, value)

    answer_spec = question["answer_spec"]
    final_answer = None
    if final_text is not None and _legal_value(final_text, answer_spec):
        final_answer = {"value": final_text}

    steps: list[dict[str, str]] = []
    for slot in question["trace_spec"]["slots"]:
        slot_id = slot["slot_id"]
        text = slot_texts.get(slot_id)
        if text is None:
            continue
        if not _legal_value(text, slot["result_spec"]):
            continue
        steps.append({"slot_id": slot_id, "value": text})

    return {
        "schema_version": config.PREDICTION_SCHEMA_VERSION,
        "dataset_version": question["dataset_version"],
        "case_id": question["case_id"],
        "final_answer": final_answer,
        "steps": steps,
    }


def predict_split(
    split: Split,
    solvers: Mapping[str, TemplateSolver],
    index: ShapeIndex,
    fallback: FallbackSolver | None = None,
    hidden_forms: Any | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Match]]:
    matches = index.identify_many(split.questions.values())
    form_answers: dict[str, Any] = {}
    if hidden_forms is not None:
        # Only questions the shape index leaves unmatched are offered to the
        # optional per-template forms (``finreason_solver.hiddenforms``).
        form_answers = hidden_forms.answer_split(
            split.questions[case_id]
            for case_id, match in matches.items()
            if match.template_id is None
        )
    records = []
    for case_id in sorted(split.questions):
        question = split.questions[case_id]
        match = matches[case_id]
        solver = solvers.get(match.template_id) if match.template_id else None
        records.append(
            predict_case(
                question,
                solver,
                fallback,
                match.template_id,
                form_answers.get(case_id) if match.template_id is None else None,
            )
        )
    return records, matches


def write_predictions(records: Iterable[Mapping[str, Any]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(
                json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            )
            handle.write("\n")
    return path

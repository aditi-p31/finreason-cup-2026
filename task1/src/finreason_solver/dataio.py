# SPDX-License-Identifier: Apache-2.0
"""Loading of the organiser's Task 1 splits into plain dicts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterator

from . import config
from .numbers import extract_numbers, gold_fraction, mask_numbers


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def index_by_case(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        case_id = row["case_id"]
        if case_id in indexed:
            raise ValueError(f"duplicate case_id {case_id}")
        indexed[case_id] = row
    return indexed


@dataclass(frozen=True)
class Instance:
    """One labelled case: question, parameters and gold values."""

    case_id: str
    template_id: str
    question: dict[str, Any]
    params: tuple[Fraction, ...]
    shape: str
    final_text: str | None
    slot_texts: tuple[str, ...]
    slot_ids: tuple[str, ...]

    @property
    def answer_spec(self) -> dict[str, Any]:
        return self.question["answer_spec"]

    @property
    def slot_specs(self) -> list[dict[str, Any]]:
        return [slot["result_spec"] for slot in self.question["trace_spec"]["slots"]]

    def slot_fraction(self, position: int) -> Fraction:
        """Exact value of slot ``position`` (0-based); numeric slots only."""

        return gold_fraction(self.slot_texts[position])

    @property
    def final_fraction(self) -> Fraction:
        assert self.final_text is not None
        return gold_fraction(self.final_text)


@dataclass(frozen=True)
class Split:
    name: str
    questions: dict[str, dict[str, Any]]
    gold: dict[str, dict[str, Any]] | None
    manifest: dict[str, dict[str, Any]] | None

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self.questions.values())


def load_split(
    questions_path: Path,
    gold_path: Path | None = None,
    manifest_path: Path | None = None,
    *,
    name: str = "",
) -> Split:
    questions = index_by_case(read_jsonl(questions_path))
    gold = index_by_case(read_jsonl(gold_path)) if gold_path else None
    manifest = index_by_case(read_jsonl(manifest_path)) if manifest_path else None
    return Split(name=name, questions=questions, gold=gold, manifest=manifest)


def load_train() -> Split:
    return load_split(
        config.TRAIN_QUESTIONS,
        config.TRAIN_GOLD,
        config.TRAIN_MANIFEST,
        name="train",
    )


def load_dev() -> Split:
    return load_split(
        config.DEV_QUESTIONS, config.DEV_GOLD, config.DEV_MANIFEST, name="dev"
    )


def load_leaderboard() -> Split:
    return load_split(config.LB_QUESTIONS, name="leaderboard")


def load_test() -> Split:
    return load_split(config.TEST_QUESTIONS, name="test")


def to_instance(
    question: dict[str, Any],
    gold: dict[str, Any] | None,
    manifest: dict[str, Any] | None,
) -> Instance:
    slots = question["trace_spec"]["slots"]
    slot_ids = tuple(slot["slot_id"] for slot in slots)
    slot_texts: tuple[str, ...] = ()
    final_text = None
    if gold is not None:
        final_text = gold["final_value"]
        slot_texts = tuple(gold["slot_values"][slot_id] for slot_id in slot_ids)
    return Instance(
        case_id=question["case_id"],
        template_id=(manifest or {}).get("template_id", ""),
        question=question,
        params=tuple(extract_numbers(question["question"])),
        shape=mask_numbers(question["question"]),
        final_text=final_text,
        slot_texts=slot_texts,
        slot_ids=slot_ids,
    )


def labelled_instances() -> dict[str, list[Instance]]:
    """Gold-labelled cases by template_id.

    Normally all 3,190 (train 2,900 + dev 290).  Under
    ``FINREASON_HOLDOUT_DEV=1`` only the 2,900 train cases, so the dev split can
    be scored as held-out data.
    """

    splits = (load_train(),) if config.HOLDOUT_DEV else (load_train(), load_dev())
    grouped: dict[str, list[Instance]] = {}
    for split in splits:
        assert split.gold is not None and split.manifest is not None
        for case_id in sorted(split.questions):
            instance = to_instance(
                split.questions[case_id],
                split.gold[case_id],
                split.manifest[case_id],
            )
            grouped.setdefault(instance.template_id, []).append(instance)
    return dict(sorted(grouped.items()))

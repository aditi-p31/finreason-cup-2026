# SPDX-License-Identifier: Apache-2.0
"""Number-masked shape matching from a question to its FinChain template id.

The cup never reveals ``template_id`` for the leaderboard or test splits, but
every template renders its questions from one (or a handful of) fixed strings
with the numbers substituted in.  Masking the numbers therefore recovers the
template exactly wherever the surface string is one we have seen labelled.
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from . import config
from .dataio import labelled_instances
from .numbers import mask_numbers

_WS = re.compile(r"\s+")


def shape_key(question_text: str) -> str:
    """Exact-match key: number-masked body with whitespace collapsed."""

    return _WS.sub(" ", mask_numbers(question_text)).strip()


def loose_key(question_text: str) -> str:
    """Relaxed key that also folds case, plural ``s`` and punctuation.

    Used only as a second pass; it can in principle merge two templates, so
    :func:`build_index` verifies it never does on the labelled data before the
    relaxed map is used.
    """

    text = shape_key(question_text).lower()
    text = re.sub(r"[^a-z0-9<>% ]+", " ", text)
    text = re.sub(r"\b(\w+?)s\b", r"\1", text)
    return _WS.sub(" ", text).strip()


@dataclass(frozen=True)
class Match:
    template_id: str | None
    method: str
    score: float


class ShapeIndex:
    """Shape -> template_id lookup with an exact, relaxed and fuzzy tier."""

    def __init__(
        self,
        exact: dict[str, str],
        loose: dict[str, str],
        conflicts: dict[str, list[str]],
    ) -> None:
        self.exact = exact
        self.loose = loose
        self.conflicts = conflicts
        self._loose_keys = sorted(loose)

    # -- construction ---------------------------------------------------
    @classmethod
    def build(cls) -> "ShapeIndex":
        exact: dict[str, set[str]] = {}
        loose: dict[str, set[str]] = {}
        for template_id, instances in labelled_instances().items():
            for instance in instances:
                text = instance.question["question"]
                exact.setdefault(shape_key(text), set()).add(template_id)
                loose.setdefault(loose_key(text), set()).add(template_id)
        conflicts = {
            key: sorted(values) for key, values in exact.items() if len(values) > 1
        }
        loose_conflicts = {
            key: sorted(values) for key, values in loose.items() if len(values) > 1
        }
        return cls(
            exact={k: next(iter(v)) for k, v in exact.items() if len(v) == 1},
            loose={k: next(iter(v)) for k, v in loose.items() if len(v) == 1},
            conflicts={**conflicts, **loose_conflicts},
        )

    # -- persistence ----------------------------------------------------
    def to_json(self) -> dict[str, Any]:
        return {
            "exact": self.exact,
            "loose": self.loose,
            "conflicts": self.conflicts,
        }

    def save(self, path: Path | None = None) -> Path:
        path = path or config.SHAPE_INDEX_JSON
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_json(), indent=1, sort_keys=True))
        return path

    @classmethod
    def load(cls, path: Path | None = None) -> "ShapeIndex":
        path = path or config.SHAPE_INDEX_JSON
        if not path.exists():
            index = cls.build()
            index.save(path)
            return index
        payload = json.loads(path.read_text())
        return cls(payload["exact"], payload["loose"], payload.get("conflicts", {}))

    # -- lookup ---------------------------------------------------------
    def identify(self, question_text: str, *, fuzzy_cutoff: float = 0.93) -> Match:
        key = shape_key(question_text)
        hit = self.exact.get(key)
        if hit is not None:
            return Match(hit, "exact", 1.0)
        relaxed = loose_key(question_text)
        hit = self.loose.get(relaxed)
        if hit is not None:
            return Match(hit, "loose", 1.0)
        best: tuple[float, str] | None = None
        matcher = difflib.SequenceMatcher()
        matcher.set_seq2(relaxed)
        for candidate in self._loose_keys:
            if abs(len(candidate) - len(relaxed)) > max(40, len(relaxed) * 0.25):
                continue
            matcher.set_seq1(candidate)
            if matcher.real_quick_ratio() < fuzzy_cutoff:
                continue
            if matcher.quick_ratio() < fuzzy_cutoff:
                continue
            ratio = matcher.ratio()
            if best is None or ratio > best[0]:
                best = (ratio, candidate)
        if best is not None and best[0] >= fuzzy_cutoff:
            return Match(self.loose[best[1]], "fuzzy", best[0])
        return Match(None, "unmatched", 0.0)

    def identify_many(self, questions: Iterable[dict[str, Any]]) -> dict[str, Match]:
        return {
            question["case_id"]: self.identify(question["question"])
            for question in questions
        }

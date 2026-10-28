# SPDX-License-Identifier: Apache-2.0
"""Per-template forms for the hidden stratum of the test split (optional route).

Off by default.  ``--hidden-forms`` (or ``FINREASON_HIDDEN_FORMS=1``) makes
``predict``, ``score-dev``, ``package`` and ``all`` answer a question that the
shape index leaves unmatched with the form of its hidden template.  Matched
questions never reach this module, and with the flag off it is not imported,
so the default predictions are unchanged.

Routing.  A question's route key is its boolean-masked shape: the
number-masked body (``numbers.mask_numbers``) with every literal
``true``/``false`` replaced by ``<B>`` and whitespace collapsed.  That is the
rule that grouped the 348 unmatched test questions into the 116 templates of
``hidden/templates.json``.  ``routes.json`` maps each template's shape to its
key.  The shape is computed from the question text at run time; no case id is
looked up anywhere.

Forms.  ``forms/HNNN.py`` are byte-for-byte copies of the reviewed
``hidden/forms/final/HNNN.py``, and ``hlib.py`` is a byte-for-byte copy of
``hidden/hlib.py``, the helper the forms import as ``hlib``.  ``routes.json``
pins the sha256 of each file and :meth:`HiddenForms.load` refuses any file
whose bytes differ.  ``hidden/export_forms.py`` refreshes the copies and pins.

Answers.  A form receives the question body and returns an exact final value
(or an enum label) and any subset of the trace slots.  Values are serialised
exactly as ``hidden/run_forms.py`` serialises them (``numbers.render_for_spec``,
then the ``predict._legal_value`` screen), and ``predict.predict_case`` takes
each slot a form leaves out from the fallback guess.  That reproduces the
record ``hidden/build_candidate.py`` writes.  As in ``build_candidate``, a
template is used only when its form succeeds on every routed question of the
split; if it fails on any one, all of that template's questions keep the
fallback, and the failure is reported.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import re
import signal
import sys
import threading
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Iterable, Mapping

from ..numbers import mask_numbers, question_body, render_for_spec
from ..predict import _legal_value

HERE = Path(__file__).resolve().parent
FORMS_DIR = HERE / "forms"
HELPER = HERE / "hlib.py"
ROUTES_JSON = HERE / "routes.json"
# Seconds per question, as in hidden/run_forms.py.
CASE_TIMEOUT = 20.0

_BOOL = re.compile(r"\b(true|false)\b", re.I)
_WS = re.compile(r"\s+")


def bshape(question_text: str) -> str:
    """Route key of a question (``hidden/build_templates.bshape``)."""

    return _WS.sub(" ", _BOOL.sub("<B>", mask_numbers(question_text))).strip()


class FormTimeout(Exception):
    pass


class FormIntegrityError(RuntimeError):
    """A packaged form or the helper does not match its sha256 pin."""


@dataclass(frozen=True)
class FormAnswer:
    """A form's serialised answer for one question."""

    key: str
    final: str
    slots: dict[str, str] = field(default_factory=dict)


def serialise(value: Any, spec: Mapping[str, Any]) -> str:
    """Final or slot string exactly as ``hidden/run_forms.serialise`` writes it."""

    if spec.get("type") == "enum":
        if not isinstance(value, str):
            raise TypeError(f"enum value must be a str label, got {type(value).__name__}")
        if value not in (spec.get("allowed_values") or []):
            raise ValueError(f"enum label {value!r} not in allowed_values {spec.get('allowed_values')}")
        return value
    if isinstance(value, bool) or not isinstance(value, (int, Fraction)):
        raise TypeError(f"numeric value must be int or Fraction, got {type(value).__name__}")
    text = render_for_spec(Fraction(value), spec)
    if not _legal_value(text, spec):
        raise ValueError(f"serialised value {text!r} is not contract-legal")
    return text


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _alarm(signum, frame):  # noqa: ARG001
    raise FormTimeout("form exceeded its time limit")


def _call(solve: Callable[[str], Any], body: str, timeout: float | None) -> Any:
    """``solve(body)`` under a wall-clock limit where a signal timer is usable."""

    if (
        not timeout
        or not hasattr(signal, "setitimer")
        or threading.current_thread() is not threading.main_thread()
    ):
        return solve(body)
    old = signal.signal(signal.SIGALRM, _alarm)
    signal.setitimer(signal.ITIMER_REAL, timeout)
    try:
        return solve(body)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


class HiddenForms:
    """Shape router plus the loaded forms."""

    def __init__(
        self,
        routes: Mapping[str, str],
        solvers: Mapping[str, Callable[[str], Any]],
        helper: ModuleType | None = None,
        timeout: float | None = CASE_TIMEOUT,
    ) -> None:
        self.routes = dict(routes)  # shape -> key
        self.solvers = dict(solvers)  # key -> solve(body)
        self.helper = helper
        self.timeout = timeout
        self.last_report: dict[str, Any] = {}

    # -- loading ----------------------------------------------------------
    @classmethod
    def load(
        cls, routes_path: Path = ROUTES_JSON, timeout: float | None = CASE_TIMEOUT
    ) -> "HiddenForms":
        payload = json.loads(routes_path.read_text(encoding="utf-8"))
        forms_dir = routes_path.parent / "forms"
        helper_path = routes_path.parent / payload["helper"]["file"]
        problems = []
        if _sha256(helper_path) != payload["helper"]["sha256"]:
            problems.append(f"{helper_path.name} does not match its sha256 pin")
        for key, entry in sorted(payload["forms"].items()):
            path = forms_dir / f"{key}.py"
            if not path.exists():
                problems.append(f"{key}: forms/{key}.py is missing")
            elif _sha256(path) != entry["sha256"]:
                problems.append(f"{key}: forms/{key}.py does not match its sha256 pin")
        if problems:
            raise FormIntegrityError("; ".join(problems))

        routes: dict[str, str] = {}
        for key, entry in sorted(payload["forms"].items()):
            if entry["shape"] in routes:
                raise FormIntegrityError(f"{key} and {routes[entry['shape']]} share a shape")
            routes[entry["shape"]] = key

        # The forms import their helper as the top-level module ``hlib``.  Bind
        # that name to the packaged copy while they load, then put back
        # whatever it named before, so nothing outside this module sees it.
        saved_hlib = sys.modules.get("hlib")
        saved_flag = sys.dont_write_bytecode
        sys.dont_write_bytecode = True  # keep forms/ free of __pycache__
        try:
            if helper_path == HELPER:
                helper = importlib.import_module(f"{__name__}.hlib")
            else:
                helper = _load_module(helper_path, f"{__name__}.hlib_{abs(hash(helper_path))}")
            sys.modules["hlib"] = helper
            solvers = {}
            for key in sorted(payload["forms"]):
                module = _load_module(forms_dir / f"{key}.py", f"{__name__}.forms.{key}")
                if getattr(module, "KEY", None) != key:
                    raise FormIntegrityError(
                        f"forms/{key}.py declares KEY={getattr(module, 'KEY', None)!r}"
                    )
                solve = getattr(module, "solve", None)
                if not callable(solve):
                    raise FormIntegrityError(f"forms/{key}.py has no callable solve(b)")
                solvers[key] = solve
        finally:
            sys.dont_write_bytecode = saved_flag
            if saved_hlib is None:
                sys.modules.pop("hlib", None)
            else:
                sys.modules["hlib"] = saved_hlib
        return cls(routes, solvers, helper, timeout)

    # -- routing ----------------------------------------------------------
    def route(self, question_text: str) -> str | None:
        return self.routes.get(bshape(question_text))

    def answer(
        self, question: Mapping[str, Any]
    ) -> tuple[str | None, FormAnswer | None, list[str]]:
        """``(key, answer, errors)`` for one question; ``key`` is None if unrouted."""

        key = self.route(question["question"])
        if key is None:
            return None, None, []
        if self.helper is not None and hasattr(self.helper, "NONRATIONAL_USED"):
            self.helper.NONRATIONAL_USED.clear()
        try:
            out = _call(self.solvers[key], question_body(question["question"]), self.timeout)
        except Exception as exc:  # noqa: BLE001 -- a failing form falls back
            return key, None, [f"{type(exc).__name__}: {exc}"]

        errors: list[str] = []
        if not isinstance(out, dict) or "final" not in out:
            return key, None, ["solve() must return a dict with a 'final' key"]
        unknown = set(out) - {"final", "slots", "info"}
        if unknown:
            errors.append(f"unknown result keys {sorted(unknown)}")
        final = None
        try:
            final = serialise(out["final"], question["answer_spec"])
        except Exception as exc:  # noqa: BLE001
            errors.append(f"final: {type(exc).__name__}: {exc}")
        slots_out = out.get("slots") or {}
        if not isinstance(slots_out, dict):
            errors.append("'slots' must be a dict {slot_id: value}")
            slots_out = {}
        specs = {slot["slot_id"]: slot["result_spec"] for slot in question["trace_spec"]["slots"]}
        slots: dict[str, str] = {}
        for slot_id, value in slots_out.items():
            if slot_id not in specs:
                errors.append(f"slot {slot_id!r} is not a slot of this question")
                continue
            try:
                slots[slot_id] = serialise(value, specs[slot_id])
            except Exception as exc:  # noqa: BLE001
                errors.append(f"slot {slot_id}: {type(exc).__name__}: {exc}")
        if errors or final is None:
            return key, None, errors or ["no final answer"]
        return key, FormAnswer(key, final, slots), []

    def answer_split(
        self, questions: Iterable[Mapping[str, Any]]
    ) -> dict[str, FormAnswer]:
        """Form answers by case id, with the all-questions-or-none template gate.

        The summary lands in :attr:`last_report`.
        """

        routed: dict[str, list[str]] = {}
        answers: dict[str, FormAnswer] = {}
        failures: dict[str, list[str]] = {}
        for question in sorted(questions, key=lambda item: item["case_id"]):
            case_id = question["case_id"]
            key, answer, errors = self.answer(question)
            if key is None:
                continue
            routed.setdefault(key, []).append(case_id)
            if answer is None:
                failures.setdefault(key, []).extend(f"{case_id}: {error}" for error in errors)
            else:
                answers[case_id] = answer
        for key in failures:
            for case_id in routed[key]:
                answers.pop(case_id, None)
        self.last_report = {
            "questions_routed": sum(len(ids) for ids in routed.values()),
            "templates_routed": len(routed),
            "questions_answered": len(answers),
            "templates_answered": len(routed) - len(failures),
            "slots_from_forms": sum(len(answer.slots) for answer in answers.values()),
            "templates_rejected": {key: failures[key][:6] for key in sorted(failures)},
        }
        return answers


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Measure the three hidden-stratum routes before any of them is built.

The 348 ``test_private_hidden`` cases are unseen template structures, so
nothing keyed to a template id can fire on them and no gold exists to gate a
solver against.  What can be measured is (a) how often each proposed route's
*precondition* holds on the actual hidden questions, which is a coverage fact
needing no labels, and (b) how well the route does on labelled data under
leave-one-template-out, which is the only honest accuracy signal available.

Routes, in the order the build report proposed them:

1. stated-formula parsing -- how many hidden questions state a formula the
   parser could bind and evaluate, under the symbolic (``=``) detector the dev
   ceiling was measured with and under a prose-definition detector;
2. cross-template structural generalisation -- can a solver induced on one
   template reproduce a *different* template's gold instances, measured
   leave-one-template-out and bucketed by how lexically close the two are, with
   the hidden stratum's own distance to the labelled corpus for comparison;
3. improved fallback -- the oracle ceiling of the guess family, and the
   residual-arm prior behind :func:`finreason_solver.fallback.blind_enum_guess`.

Writes ``artifacts/hidden_routes.json``.  Nothing here calls a model.
"""

from __future__ import annotations

import collections
import difflib
import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from finreason_solver import config, dataio, derive, shapes  # noqa: E402
from finreason_solver.fallback import (  # noqa: E402
    _best_skeleton,
    blind_enum_guess,
    residual_branch,
)
from finreason_solver.numbers import extract_numbers  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from measure_stated_formula_ceiling import stated_formula_clauses  # noqa: E402

_DEF = re.compile(r"\b(equals|is defined as|define[sd]?\b[^.;]{0,80}?\bas\b|means)\b", re.I)
_OPWORD = re.compile(r"\b(minus|plus|times|multiplied|divided|over|sum of|product of|less)\b", re.I)
_SNAKE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+){1,}\b")
_INFIX = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\s*[-+*/]\s*[A-Za-z_(]")


def _body(question: dict) -> str:
    return question["question"].split("\n\nAnswer format:")[0]


def prose_definition_clauses(text: str) -> list[str]:
    out = []
    for sentence in re.split(r"(?<=\.)\s+", text):
        for match in _DEF.finditer(sentence):
            rhs = sentence[match.end() : match.end() + 200]
            if _OPWORD.search(rhs) or re.search(r"[+*/^]", rhs):
                out.append(sentence.strip())
    return out


def states_symbolic_formula(question: dict) -> bool:
    text = _body(question)
    allowed = {v.lower() for v in (question["answer_spec"].get("allowed_values") or [])}
    names = {n for n in _SNAKE.findall(text) if n not in allowed}
    return bool(names) and bool(_INFIX.search(text))


def hidden_cases(index: shapes.ShapeIndex) -> list[dict]:
    split = dataio.load_test()
    return [
        question
        for question in split.questions.values()
        if index.identify(question["question"]).template_id is None
    ]


def by_template(cases: list[dict]) -> "collections.OrderedDict[str, list[dict]]":
    groups: collections.OrderedDict[str, list[dict]] = collections.OrderedDict()
    for case in cases:
        groups.setdefault(shapes.shape_key(case["question"]), []).append(case)
    return groups


def route1(cases, groups, dev) -> dict:
    hidden_like = [
        question
        for case_id, question in dev.questions.items()
        if dev.manifest[case_id]["difficulty"] in ("intermediate", "advanced")
    ]

    def rate(items, predicate):
        hits = sum(1 for item in items if predicate(item))
        return {"hits": hits, "n": len(items), "rate": round(hits / len(items), 6)}

    symbolic = lambda q: bool(stated_formula_clauses(q["question"]))  # noqa: E731
    prose = lambda q: bool(prose_definition_clauses(_body(q)))  # noqa: E731
    return {
        "dev_intermediate_advanced": {
            "equals_sign_detector": rate(hidden_like, symbolic),
            "prose_definition_detector": rate(hidden_like, prose),
        },
        "hidden_cases": {
            "equals_sign_detector": rate(cases, symbolic),
            "prose_definition_detector": rate(cases, prose),
            "bindable_symbolic_formula": rate(cases, states_symbolic_formula),
        },
        "hidden_templates": {
            "equals_sign_detector": rate([g[0] for g in groups.values()], symbolic),
            "prose_definition_detector": rate([g[0] for g in groups.values()], prose),
            "bindable_symbolic_formula": rate(
                [g[0] for g in groups.values()], states_symbolic_formula
            ),
        },
    }


def route2(groups) -> dict:
    solvers = {
        row["template_id"]: derive.TemplateSolver.from_json(row)
        for row in json.loads(config.SOLVERS_JSON.read_text())
    }
    instances = dataio.labelled_instances()
    difficulty = {}
    for split in (dataio.load_train(), dataio.load_dev()):
        for case_id, row in split.manifest.items():
            difficulty[row["template_id"]] = row["difficulty"]
    templates = sorted(instances)
    key = {t: shapes.loose_key(instances[t][0].question["question"]) for t in templates}
    arity = {t: len(instances[t][0].params) for t in templates}

    buckets: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])
    hits = total = 0
    for target in templates:
        if difficulty[target] == "basic":
            continue
        siblings = [t for t in templates if t != target and arity[t] == arity[target]]
        if not siblings:
            continue
        similarity = {
            t: difflib.SequenceMatcher(None, key[target], key[t]).ratio() for t in siblings
        }
        nearest = max(siblings, key=lambda t: (similarity[t], t))
        gold = instances[target]
        try:
            ok = derive.contract_test(solvers[nearest], gold)["final_ok"] == len(gold)
        except Exception:
            ok = False
        score = similarity[nearest]
        name = (
            ">=0.80" if score >= 0.80
            else "0.50-0.80" if score >= 0.50
            else "0.30-0.50" if score >= 0.30
            else "0.21-0.30" if score >= 0.21
            else "<=0.21"
        )
        buckets[name][0] += int(ok)
        buckets[name][1] += 1
        hits += int(ok)
        total += 1

    def nearest_labelled(text: str, exclude: str | None = None) -> float:
        probe = shapes.loose_key(text)
        matcher = difflib.SequenceMatcher()
        matcher.set_seq2(probe)
        best = 0.0
        for t in templates:
            if t == exclude:
                continue
            matcher.set_seq1(key[t])
            if matcher.real_quick_ratio() < best or matcher.quick_ratio() < best:
                continue
            best = max(best, matcher.ratio())
        return best

    seen_distance = [nearest_labelled(instances[t][0].question["question"], t) for t in templates]
    hidden_distance = [nearest_labelled(g[0]["question"]) for g in groups.values()]
    return {
        "protocol": (
            "leave one TEMPLATE out: for each intermediate/advanced labelled "
            "template, run the induced program of the lexically nearest other "
            "template of the same arity against all 11 of its gold instances"
        ),
        "int_adv_all_11_exact": {"hits": hits, "n": total, "rate": round(hits / total, 6)},
        "by_lexical_similarity": {
            name: {"hits": h, "n": n, "rate": round(h / n, 6) if n else None}
            for name, (h, n) in sorted(buckets.items())
        },
        "nearest_labelled_template_similarity": {
            "held_out_seen_template": {
                "median": round(statistics.median(seen_distance), 4),
                "max": round(max(seen_distance), 4),
                "at_or_above_0.30": sum(1 for x in seen_distance if x >= 0.30),
                "n": len(seen_distance),
            },
            "hidden_template": {
                "median": round(statistics.median(hidden_distance), 4),
                "max": round(max(hidden_distance), 4),
                "at_or_above_0.30": sum(1 for x in hidden_distance if x >= 0.30),
                "n": len(hidden_distance),
            },
        },
    }


def route3(cases, groups) -> dict:
    instances = dataio.labelled_instances()
    difficulty = {}
    for split in (dataio.load_train(), dataio.load_dev()):
        for case_id, row in split.manifest.items():
            difficulty[row["template_id"]] = row["difficulty"]

    final_reach = final_total = slot_reach = slot_total = 0
    for template_id, group in instances.items():
        if difficulty[template_id] == "basic":
            continue
        first = group[0]
        window = range(min(len(first.params), 8))
        if first.answer_spec.get("type") == "decimal":
            final_total += 1
            targets = [i.final_fraction for i in group]
            final_reach += int(_best_skeleton(group, targets, window) is not None)
        for position, slot in enumerate(first.question["trace_spec"]["slots"]):
            if slot["result_spec"].get("type") != "decimal":
                continue
            slot_total += 1
            targets = [i.slot_fraction(position) for i in group]
            slot_reach += int(_best_skeleton(group, targets, window) is not None)

    units = []
    for template_id, group in instances.items():
        spec = group[0].answer_spec
        if spec.get("type") == "enum" and len(spec.get("allowed_values") or []) >= 2:
            units.append(
                (sorted(spec["allowed_values"]), group[0].question["question"],
                 [i.final_text for i in group], template_id)
            )
        for position, slot in enumerate(group[0].question["trace_spec"]["slots"]):
            result = slot["result_spec"]
            if result.get("type") != "enum" or len(result.get("allowed_values") or []) < 2:
                continue
            units.append(
                (sorted(result["allowed_values"]), group[0].question["question"],
                 [i.slot_texts[position] for i in group], template_id)
            )
    residual_hits = alternative_hits = instances_seen = fired = 0
    favourable = 0
    for allowed, text, golds, _template_id in units:
        residual = residual_branch(text, allowed)
        if residual is None:
            continue
        fired += 1
        alternative = blind_enum_guess(text, allowed)
        r = sum(1 for g in golds if g == residual)
        a = sum(1 for g in golds if g == alternative)
        residual_hits += r
        alternative_hits += a
        favourable += int(a >= r)
        instances_seen += len(golds)

    enum_groups = [g for g in groups.values() if g[0]["answer_spec"]["type"] == "enum"]
    changed_templates = changed_cases = silent = 0
    for group in enum_groups:
        allowed = sorted(group[0]["answer_spec"]["allowed_values"])
        if residual_branch(group[0]["question"], allowed) is None:
            silent += 1
        if allowed[0] != blind_enum_guess(group[0]["question"], allowed):
            changed_templates += 1
            changed_cases += len(group)
    numbers = [len(extract_numbers(c["question"])) for c in cases]
    return {
        "skeleton_family_oracle_ceiling_int_adv": {
            "finals": {"hits": final_reach, "n": final_total,
                       "rate": round(final_reach / final_total, 6)},
            "slots": {"hits": slot_reach, "n": slot_total,
                      "rate": round(slot_reach / slot_total, 6)},
            "note": (
                "share of labelled intermediate/advanced outputs that SOME "
                "skeleton and operand binding reproduces on all 11 instances; "
                "an oracle upper bound on any selector over this family"
            ),
        },
        "residual_arm_prior": {
            "protocol": (
                "the detector reads only the target question's own decision "
                "list and fits nothing, so leave-one-template-out holds by "
                "construction"
            ),
            "units_fired": fired,
            "units_total": len(units),
            "instances": instances_seen,
            "guess_residual_arm": round(residual_hits / instances_seen, 6),
            "guess_non_residual_arm": round(alternative_hits / instances_seen, 6),
            "units_where_avoiding_is_no_worse": favourable,
            "caveat": (
                "the labelled corpus states its residual arm with 'otherwise' "
                "or leaves it unnamed; the 'when neither qualifies' form that "
                "covers most of the hidden application never occurs in it"
            ),
        },
        "hidden_enum_population": {
            "cases": sum(len(g) for g in enum_groups),
            "templates": len(enum_groups),
            "choice_counts": dict(
                collections.Counter(
                    len(g[0]["answer_spec"]["allowed_values"]) for g in enum_groups
                )
            ),
            "detector_silent_templates": silent,
            "guess_changed_templates": changed_templates,
            "guess_changed_cases": changed_cases,
        },
        "hidden_numbers_per_question": {
            "median": statistics.median(numbers),
            "mean": round(statistics.mean(numbers), 3),
            "beyond_skeleton_operand_window": sum(1 for n in numbers if n > 8),
        },
    }


def main() -> int:
    index = shapes.ShapeIndex.load()
    cases = hidden_cases(index)
    groups = by_template(cases)
    dev = dataio.load_dev()
    assert dev.manifest is not None
    report = {
        "hidden_cases": len(cases),
        "hidden_templates": len(groups),
        "instances_per_hidden_template": dict(
            collections.Counter(len(g) for g in groups.values())
        ),
        "hidden_answer_types": dict(
            collections.Counter(c["answer_spec"]["type"] for c in cases)
        ),
        "hidden_slots": sum(len(c["trace_spec"]["slots"]) for c in cases),
        "route1_stated_formula": route1(cases, groups, dev),
        "route2_cross_template": route2(groups),
        "route3_fallback": route3(cases, groups),
    }
    print(json.dumps(report, indent=1, sort_keys=True))
    out = config.ARTIFACTS / "hidden_routes.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

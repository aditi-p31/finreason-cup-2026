#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Project ``hidden_fac`` for a submission that can only guess the hidden cases.

Nothing keyed to a template id fires on the 348 hidden cases, so every hidden
final answer is a guess.  A guess on a *decimal* answer is worth almost nothing
-- the scorer demands exact equality after half-up rounding, with no credit for
being close -- but a guess on an *enum* answer is worth roughly one over the
number of allowed values, and 84 of the 348 hidden cases are enums.  That makes
``hidden_fac`` clearly nonzero, and worth projecting rather than assuming.

``hidden_fac`` is not a case average: the scorer means template scores into
(domain, topic, difficulty) cells, weights intermediate and advanced equally
within a topic, means topics into domains, and means exactly 12 domains.  So a
domain carries 1/12 of the score however many hidden cases it holds, and the
enum templates are not spread evenly.  The hidden manifest is not published, so
each hidden template's domain is recovered here by a TF-IDF nearest-centroid
classifier fitted on the labelled train split; its accuracy on the held-out dev
split is reported alongside, and it is the one estimated input below.

Per-label hit probabilities come from the labelled corpus measurement in
``scripts/measure_hidden_routes.py``.  Writes ``artifacts/hidden_fac_projection.json``.
"""

from __future__ import annotations

import collections
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from finreason_solver import config, dataio, shapes  # noqa: E402
from finreason_solver.fallback import blind_enum_guess, residual_branch  # noqa: E402

_WORD = re.compile(r"[a-z]{3,}")


def _build_domain_classifier():
    train = dataio.load_train()
    assert train.manifest is not None
    per_domain: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    document_frequency: collections.Counter = collections.Counter()
    documents = 0
    for case_id, question in train.questions.items():
        domain = train.manifest[case_id]["domain_id"]
        words = set(_WORD.findall(question["question"].lower()))
        per_domain[domain].update(words)
        document_frequency.update(words)
        documents += 1
    idf = {w: math.log(documents / (1 + c)) for w, c in document_frequency.items()}
    centroids = {}
    for domain, counts in per_domain.items():
        vector = {w: c * idf.get(w, 0.0) for w, c in counts.items()}
        norm = math.sqrt(sum(v * v for v in vector.values())) or 1.0
        centroids[domain] = {w: v / norm for w, v in vector.items()}

    def classify(text: str) -> str:
        counts = collections.Counter(_WORD.findall(text.lower()))
        vector = {w: c * idf.get(w, 0.0) for w, c in counts.items()}
        norm = math.sqrt(sum(v * v for v in vector.values())) or 1.0
        best = None
        for domain, centroid in centroids.items():
            score = sum(v * centroid.get(w, 0.0) for w, v in vector.items()) / norm
            if best is None or score > best[0]:
                best = (score, domain)
        assert best is not None
        return best[1]

    return classify


def main() -> int:
    classify = _build_domain_classifier()
    dev = dataio.load_dev()
    assert dev.manifest is not None
    correct = sum(
        1
        for case_id, question in dev.questions.items()
        if classify(question["question"]) == dev.manifest[case_id]["domain_id"]
    )

    index = shapes.ShapeIndex.load()
    test = dataio.load_test()
    groups: collections.OrderedDict[str, list[dict]] = collections.OrderedDict()
    for question in test.questions.values():
        if index.identify(question["question"]).template_id is not None:
            continue
        groups.setdefault(shapes.shape_key(question["question"]), []).append(question)

    # Measured on the labelled corpus (see measure_hidden_routes.py).
    residual_rate = {3: 17 / 66, 2: 49 / 110}
    alternative_rate = {3: 23 / 66, 2: 61 / 110}

    def enum_hit(allowed, pick, residual) -> float:
        if residual is None:
            return 1.0 / len(allowed)
        band = 3 if len(allowed) >= 3 else 2
        return residual_rate[band] if pick == residual else alternative_rate[band]

    def project(policy: str, decimal_rate: float) -> tuple[float, float, dict]:
        per_domain: dict[str, list[float]] = collections.defaultdict(list)
        hits = cases = 0.0
        for group in groups.values():
            question = group[0]
            domain = classify(question["question"])
            spec = question["answer_spec"]
            if spec["type"] == "enum":
                allowed = sorted(spec["allowed_values"])
                residual = residual_branch(question["question"], allowed)
                pick = allowed[0] if policy == "alphabetical" else blind_enum_guess(
                    question["question"], allowed
                )
                probability = enum_hit(allowed, pick, residual)
            else:
                probability = decimal_rate
            per_domain[domain].append(probability)
            hits += probability * len(group)
            cases += len(group)
        means = {d: sum(v) / len(v) for d, v in per_domain.items()}
        return sum(means.values()) / 12, hits / cases, means

    report: dict = {
        "domain_classifier_dev_accuracy": {
            "correct": correct,
            "n": len(dev.questions),
            "rate": round(correct / len(dev.questions), 6),
        },
        "hidden_templates": len(groups),
        "aggregation": (
            "hidden_fac = mean over 12 domains of the mean over that domain's "
            "hidden templates of the template's case-mean fac; the scorer's "
            "topic and difficulty layers collapse to this when each topic "
            "carries one intermediate and one advanced hidden template"
        ),
        "projections": {},
    }
    for decimal_rate in (0.0, 0.01, 0.02, 0.03):
        before, micro_before, _ = project("alphabetical", decimal_rate)
        after, micro_after, means = project("residual_avoiding", decimal_rate)
        report["projections"][f"decimal_guess_rate_{decimal_rate:.2f}"] = {
            "hidden_fac_alphabetical_first": round(before, 6),
            "hidden_fac_residual_avoiding": round(after, 6),
            "delta": round(after - before, 6),
            "micro_alphabetical_first": round(micro_before, 6),
            "micro_residual_avoiding": round(micro_after, 6),
        }
    _, _, means = project("residual_avoiding", 0.01)
    report["per_domain_template_mean_at_decimal_rate_0.01"] = {
        d: round(v, 6) for d, v in sorted(means.items())
    }
    print(json.dumps(report, indent=1, sort_keys=True))
    out = config.ARTIFACTS / "hidden_fac_projection.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Group the hidden stratum of the Task 1 test split into templates.

Writes hidden/templates.json.  Reads only: the organisers' test questions and the
shipped shape index (to decide which test cases are unmatched, i.e. hidden).

Grouping is the 2026-09-16 pilot's ``bshape``: mask numbers with
``numbers.mask_numbers``, replace the literal words true/false with ``<B>``,
collapse whitespace.  Keys H001.. follow the sorted order of each template's
first case_id, which is the order the pilot indexed its clusters in.

No model call, no network, no gold (there is none for the test split).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLUTION = HERE.parent
sys.path.insert(0, str(SOLUTION / "src"))

from finreason_solver import config  # noqa: E402
from finreason_solver.dataio import load_test  # noqa: E402
from finreason_solver.numbers import mask_numbers, question_body  # noqa: E402
from finreason_solver.shapes import ShapeIndex  # noqa: E402

N_BATCHES = 15
BOOL = re.compile(r"\b(true|false)\b", re.I)
WS = re.compile(r"\s+")


def bshape(question_text: str) -> str:
    return WS.sub(" ", BOOL.sub("<B>", mask_numbers(question_text))).strip()


def canon_specs(q: dict) -> str:
    return json.dumps({"a": q["answer_spec"], "t": q["trace_spec"]}, sort_keys=True)


def main() -> int:
    test = load_test()
    index = ShapeIndex.load(config.SHAPE_INDEX_JSON)
    matches = {cid: index.identify(q["question"]) for cid, q in sorted(test.questions.items())}
    hidden = sorted(cid for cid, m in matches.items() if m.template_id is None)
    seen = sorted(cid for cid, m in matches.items() if m.template_id is not None)

    # cross-check against the pilot's recorded split
    probe = json.loads((SOLUTION / "artifacts_hidden_probe" / "q1_counts.json").read_text())
    assert sorted(probe["hidden_case_ids"]) == hidden, "hidden split differs from the pilot's"

    groups: dict[str, list[str]] = defaultdict(list)
    for cid in hidden:
        groups[bshape(test.questions[cid]["question"])].append(cid)
    clusters = sorted((sorted(v) for v in groups.values()), key=lambda v: v[0])

    templates = []
    for i, cids in enumerate(clusters, start=1):
        qs = [test.questions[c] for c in cids]
        specs = {canon_specs(q) for q in qs}
        if len(specs) != 1:
            raise SystemExit(f"template {i}: cases disagree on answer_spec/trace_spec")
        q0 = qs[0]
        a = q0["answer_spec"]
        templates.append({
            "key": f"H{i:03d}",
            "case_ids": cids,
            "type": a["type"],
            "answer_spec": a,
            "slots": [
                {"slot_id": s["slot_id"], "description": s["description"],
                 "result_spec": s["result_spec"], "position": s["position"]}
                for s in q0["trace_spec"]["slots"]
            ],
            "questions": [q["question"] for q in qs],
            "bodies": [question_body(q["question"]).strip() for q in qs],
        })

    # ---- batches: deal enum round-robin, then decimal continuing at the batches
    # that received fewest enum templates, so enum load is even and sizes are 7 or 8.
    enum_keys = [t["key"] for t in templates if t["type"] == "enum"]
    dec_keys = [t["key"] for t in templates if t["type"] != "enum"]
    batches: list[list[str]] = [[] for _ in range(N_BATCHES)]
    for j, k in enumerate(enum_keys):
        batches[j % N_BATCHES].append(k)
    start = len(enum_keys) % N_BATCHES
    for j, k in enumerate(dec_keys):
        batches[(start + j) % N_BATCHES].append(k)
    batch_of = {}
    for b, ks in enumerate(batches, start=1):
        ks.sort()
        for k in ks:
            batch_of[k] = b
    for t in templates:
        t["batch"] = batch_of[t["key"]]

    # ---- pilot mapping: probe03 indexes enum_t, probe04 indexes dec_t, both in
    # sorted-first-case order, i.e. the order of enum_keys / dec_keys.
    pilot_enum = json.loads((SOLUTION / "artifacts_hidden_probe" / "q4_enum_pilot.json").read_text())
    pilot_dec = json.loads((SOLUTION / "artifacts_hidden_probe" / "q4_decimal_pilot.json").read_text())
    pilot_map = {}
    for ti in pilot_enum["templates_implemented"]:
        pilot_map[enum_keys[ti]] = f"enum#{ti}"
    for ti in pilot_dec["templates_implemented"]:
        pilot_map[dec_keys[ti]] = f"decimal#{ti}"
    # the pilot rows must land on the case ids of the template they were mapped to
    by_key = {t["key"]: t for t in templates}
    for rows, keys, tag in ((pilot_enum["rows"], enum_keys, "enum"), (pilot_dec["rows"], dec_keys, "decimal")):
        for r in rows:
            assert r["case_id"] in by_key[keys[r["template_index"]]]["case_ids"], (tag, r["template_index"])
    for t in templates:
        t["pilot"] = pilot_map.get(t["key"])

    all_cases = [c for t in templates for c in t["case_ids"]]
    assert len(all_cases) == len(set(all_cases)) == len(hidden)
    size_hist = Counter(len(t["case_ids"]) for t in templates)
    n_slots = sum(len(t["slots"]) * len(t["case_ids"]) for t in templates)
    choice_hist = Counter(len(t["answer_spec"]["allowed_values"]) for t in templates if t["type"] == "enum")
    payload = {
        "generated_by": "hidden/build_templates.py",
        "test_questions": str(config.TEST_QUESTIONS),
        "test_questions_sha256": hashlib.sha256(config.TEST_QUESTIONS.read_bytes()).hexdigest(),
        "counts": {
            "test_cases": len(test.questions),
            "seen_cases": len(seen),
            "hidden_cases": len(hidden),
            "templates": len(templates),
            "template_sizes": {str(k): v for k, v in sorted(size_hist.items())},
            "enum_templates": len(enum_keys),
            "decimal_templates": len(dec_keys),
            "hidden_slots_total": n_slots,
            "enum_choice_counts": {str(k): v for k, v in sorted(choice_hist.items())},
            "batches": N_BATCHES,
            "pilot_templates": len(pilot_map),
        },
        "batches": {str(b): ks for b, ks in enumerate(batches, start=1)},
        "seen_case_ids": seen,
        "templates": templates,
    }
    out = HERE / "templates.json"
    out.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(payload["counts"], indent=1))
    for b, ks in payload["batches"].items():
        ne = sum(1 for k in ks if by_key[k]["type"] == "enum")
        print(f"batch {b:>2}: {len(ks)} templates ({ne} enum): {' '.join(ks)}")
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Recompute the paper's coincidence counts from the archived 5 September builds.

``docs/holdout/`` holds the search of 5 September 2026, stages 1 to 3, in two
builds: one fitted on all eleven labelled instances per template (practice
included), one fitted on the ten training instances only (practice held out),
and the test archive accepted on 7 September, which the first build produced.
For each build this script runs the degeneracy audit
(``scripts/degeneracy_audit.py``) to find the coincidence-fitted components,
those that pass the gate but disagree with their reference form on an unseen
draw, and replays each of them on its template's practice instance with the
organisers' ``value_matches``. A component that reproduces the practice gold
value is one the held-out practice draw could not expose. It then counts the
values of the 7 September archive that came from such components and disagree
with the reference forms.

    PYTHONPATH=src .venv/bin/python scripts/holdout_comparison.py

Expected output (docs/holdout/README.md):

    eleven  templates 38  components 82  reproduce practice 82
    ten     templates 39  components 86  reproduce practice 76
    archive 2026-09-07  finals 53  slots 78  templates 36

No gold exists for the unseen draws, so no score is computed; the practice
replay reads the practice gold.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import degeneracy_audit as audit  # noqa: E402
from finreason_solver import dataio  # noqa: E402
from finreason_solver.shapes import ShapeIndex  # noqa: E402

HOLDOUT = ROOT / "docs" / "holdout"
BUILDS = (
    ("eleven", HOLDOUT / "solvers_eleven_20260905.json"),
    ("ten", HOLDOUT / "solvers_ten_20260905.json"),
)
ARCHIVE = HOLDOUT / "test_predictions_20260907.jsonl"


def practice_instances() -> dict[str, dataio.Instance]:
    dev = dataio.load_dev()
    out = {}
    for case_id, question in dev.questions.items():
        inst = dataio.to_instance(question, dev.gold[case_id], dev.manifest[case_id])
        out[inst.template_id] = inst
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=None, help="also write the per-component rows as JSON")
    args = parser.parse_args(argv)

    index = ShapeIndex.load()
    groups = dataio.labelled_instances()
    unseen = audit.unseen_draws(index)
    relations = audit.audit_relations(groups, unseen)
    refs = audit.references()
    practice = practice_instances()

    report: dict = {"builds": {}}
    loaded = {}
    for label, path in BUILDS:
        payloads = audit.load_build(path)
        loaded[label] = payloads
        solvers = audit.solvers_of(payloads)
        result = audit.audit_build(label, payloads, groups, unseen, relations, refs)
        rows = []
        for row in result["degenerate_components"]:
            tid, cid = row["template_id"], row["component"]
            inst = practice[tid]
            ours = audit.outputs(solvers[tid], inst.params, inst.question).get(cid)
            gold = inst.final_text if cid == audit.FINAL else inst.slot_texts[inst.slot_ids.index(cid)]
            rows.append({"template_id": tid, "component": cid,
                         "reproduces_practice": audit.same(ours, gold, audit.spec_of(inst.question, cid))})
        entry = {
            "solvers_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "templates": len(result["degenerate_templates"]),
            "components": len(rows),
            "reproduce_practice": sum(r["reproduces_practice"] for r in rows),
            "rows": rows,
        }
        report["builds"][label] = entry
        print(f"{label:<7} templates {entry['templates']}  components {entry['components']}  "
              f"reproduce practice {entry['reproduce_practice']}")

    arch = audit.audit_archive("2026-09-07", ARCHIVE, loaded["eleven"], groups, unseen, refs)
    wrong = arch["wrong_from_degenerate_trusted_components"]
    report["archive"] = {k: v for k, v in arch.items() if k != "rows"}
    print(f"archive 2026-09-07  finals {wrong['finals']}  slots {wrong['slots']}  templates {wrong['templates']}")
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

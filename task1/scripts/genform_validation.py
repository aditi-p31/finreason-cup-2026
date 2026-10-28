#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Per-template evidence for the stage-4 generator-recovered forms.

Writes ``artifacts/genform_validation.json``: for each of the eleven forms, the
FinChain generator it was read from, the recovered arithmetic in readable form,
the full 11-instance contract test, and a held-out replay that derives nothing
from the dev instance and then checks it.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from finreason_solver import build_solvers, config, expr as E, genforms  # noqa: E402
from finreason_solver.dataio import (  # noqa: E402
    load_dev,
    load_train,
    to_instance,
)
from finreason_solver.derive import (  # noqa: E402
    TemplateSolver,
    contract_test,
)


def _grouped(splits):
    grouped: dict[str, list] = {}
    for split in splits:
        assert split.gold is not None and split.manifest is not None
        for case_id in sorted(split.questions):
            instance = to_instance(
                split.questions[case_id], split.gold[case_id], split.manifest[case_id]
            )
            grouped.setdefault(instance.template_id, []).append(instance)
    return grouped


def main() -> int:
    train = load_train()
    dev = load_dev()
    all_instances = _grouped([train, dev])
    train_only = _grouped([train])
    dev_only = _grouped([dev])

    payloads = {
        item["template_id"]: item
        for item in json.loads(config.SOLVERS_JSON.read_text())
    }

    rows = []
    for template_id in sorted(genforms.FORMS):
        form = genforms.FORMS[template_id]
        incumbent = TemplateSolver.from_json(payloads[template_id])
        instances = all_instances[template_id]
        candidate = genforms.candidate_solver(form, incumbent, instances)
        report = contract_test(candidate, instances)
        # Held out: the same written-down form, replayed against the ten train
        # instances and then against the dev instance it never touched.  The
        # form is not fitted to anything, so both must be perfect.
        train_report = contract_test(candidate, train_only[template_id])
        dev_report = contract_test(candidate, dev_only[template_id])
        before = payloads[template_id].get("contract_test") or {}
        n = before.get("n_instances", 0)
        rows.append(
            {
                "template_id": template_id,
                "finchain_generator": form.source,
                "recovered": form.note,
                "slots": {
                    slot.slot_id: E.to_text(slot.expression)
                    for slot in candidate.slots
                },
                "final": E.to_text(candidate.final_expression),
                "contract_test": report,
                "train_only_contract_test": train_report,
                "dev_only_contract_test": dev_report,
                "ships": bool(report["final_perfect"] and report["slots_perfect"]),
                "before": {
                    "final_perfect": bool(before.get("final_perfect")),
                    "slots_validated": sum(
                        1 for count in (before.get("slot_ok") or {}).values()
                        if count == n
                    ),
                    "n_slots": before.get("n_slots", 0),
                },
            }
        )

    shipped = [row for row in rows if row["ships"]]
    slots_before = sum(row["before"]["slots_validated"] for row in rows)
    slots_after = sum(row["contract_test"]["n_slots"] for row in rows if row["ships"])
    validated_before = sum(
        1 for item in payloads.values() if build_solvers.is_shippable(item)
    )
    summary = {
        "forms_registered": len(rows),
        "forms_shipping": len(shipped),
        "forms_resisting": sorted(
            row["template_id"] for row in rows if not row["ships"]
        ),
        "held_out_dev_finals_matched": sum(
            row["dev_only_contract_test"]["final_ok"] for row in rows
        ),
        "held_out_dev_slots_matched": sum(
            sum(row["dev_only_contract_test"]["slot_ok"].values()) for row in rows
        ),
        "held_out_dev_slots_expected": sum(
            row["contract_test"]["n_slots"] for row in rows
        ),
        "templates_validated_before": validated_before,
        "templates_validated_after": validated_before + len(shipped),
        "slot_definitions_validated_delta": slots_after - slots_before,
    }
    payload = {"summary": summary, "rows": rows}
    out = config.ARTIFACTS / "genform_validation.json"
    out.write_text(json.dumps(payload, indent=1, sort_keys=True))
    print(json.dumps(summary, indent=1, sort_keys=True))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

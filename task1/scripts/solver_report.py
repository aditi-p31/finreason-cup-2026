#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Per-template contract-test summary for the build report."""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from finreason_solver import build_solvers, config, dataio  # noqa: E402


def main() -> int:
    payloads = json.loads(config.SOLVERS_JSON.read_text())
    groups = dataio.labelled_instances()
    manifest = dataio.load_dev().manifest or {}
    domain_of = {
        row["template_id"]: (row["domain_id"], row["topic_id"], row["difficulty"])
        for row in manifest.values()
    }

    rows = []
    for payload in payloads:
        template_id = payload["template_id"]
        report = payload.get("contract_test") or {}
        n = report.get("n_instances", 0)
        slot_ok = report.get("slot_ok", {})
        domain, topic, difficulty = domain_of.get(template_id, ("", "", ""))
        rows.append(
            {
                "template_id": template_id,
                "domain": domain,
                "topic": topic,
                "difficulty": difficulty,
                "stage": payload.get("stage", 1),
                "n_slots": len(slot_ok),
                "slots_validated": sum(1 for count in slot_ok.values() if count == n),
                "final_validated": bool(report.get("final_perfect")),
                "fully_validated": build_solvers.is_shippable(payload),
                "seconds": payload.get("seconds"),
            }
        )

    full = [row for row in rows if row["fully_validated"]]
    final_only = [row for row in rows if row["final_validated"]]
    slots_total = sum(row["n_slots"] for row in rows)
    slots_validated = sum(row["slots_validated"] for row in rows)

    by_domain = collections.defaultdict(lambda: [0, 0])
    for row in rows:
        bucket = by_domain[row["domain"]]
        bucket[0] += int(row["fully_validated"])
        bucket[1] += 1

    summary = {
        "templates": len(rows),
        "fully_validated": len(full),
        "final_answer_validated": len(final_only),
        "slot_definitions": slots_total,
        "slot_definitions_validated": slots_validated,
        "by_domain": {
            domain: {"validated": counts[0], "templates": counts[1]}
            for domain, counts in sorted(by_domain.items())
        },
        "by_difficulty": {
            difficulty: {
                "validated": sum(
                    1
                    for row in rows
                    if row["difficulty"] == difficulty and row["fully_validated"]
                ),
                "templates": sum(1 for row in rows if row["difficulty"] == difficulty),
            }
            for difficulty in ("basic", "intermediate", "advanced")
        },
        "unsolved_final": sorted(
            row["template_id"] for row in rows if not row["final_validated"]
        ),
        "unsolved_slots": sorted(
            row["template_id"]
            for row in rows
            if row["slots_validated"] < row["n_slots"]
        ),
    }
    print(json.dumps(summary, indent=1, sort_keys=True))
    out = config.ARTIFACTS / "solver_report.json"
    out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

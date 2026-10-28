#!/usr/bin/env python3
"""Score a predictions file on one slice of the practice set with the kit's
deterministic judge (configs/deterministic_evaluation.yaml), offline, no API.

    python3 tools/score_split.py --predictions P.jsonl --subset devset
    python3 tools/score_split.py --predictions P.jsonl --subset all --output-dir runs/x

--subset is one of: all, devset, holdout, holdout_unseen_filer,
devset_untruncated, holdout_untruncated (from split.json).
Gold is filtered in memory; no per-split gold file is ever written, so HOLDOUT
gold is only touched when --subset holdout* is asked for explicitly.
Predictions outside the subset are ignored. Missing predictions inside the
subset are an error (official policy is invalid_submission).

The kit (the organizers' starter kit with its data/) is ./kit, or the
directory named by the FINREASON_TASK3_KIT environment variable.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIT = Path(os.environ.get("FINREASON_TASK3_KIT") or (ROOT / "kit")).resolve()
sys.path.insert(0, str(KIT))

from evaluation.config import EvaluationConfig  # noqa: E402
from evaluation.evaluator import evaluate  # noqa: E402
from task3_core.io import load_gold, load_predictions  # noqa: E402

GOLD = KIT / "data" / "public_dev.jsonl"
SPLIT = ROOT / "split.json"
CONFIG = KIT / "configs" / "deterministic_evaluation.yaml"
SUBSETS = ("devset", "holdout", "holdout_unseen_filer", "devset_untruncated", "holdout_untruncated")


def subset_ids(name: str, gold_ids):
    if name == "all":
        return list(gold_ids)
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    if name not in SUBSETS:
        raise SystemExit(f"unknown subset {name!r}")
    return list(split[name])


def score(predictions_path: str, subset: str, output_dir: str | None = None, name: str | None = None):
    gold = load_gold(GOLD)
    ids = subset_ids(subset, gold)
    preds, errors = load_predictions(predictions_path)
    if errors:
        raise SystemExit(f"prediction load errors: {errors[:5]}")
    missing = [i for i in ids if i not in preds]
    if missing:
        raise SystemExit(f"{len(missing)} prediction(s) missing in subset {subset}: {missing[:10]}")
    config = EvaluationConfig.load(CONFIG)
    config.judge.provider = "deterministic"
    config.missing_prediction_policy = "invalid_submission"
    run = evaluate(
        {i: gold[i] for i in ids},
        {i: preds[i] for i in ids},
        config,
        case_ids=ids,
        submission_name=name or Path(predictions_path).stem,
        predictions_path=predictions_path,
        show_progress=False,
    )
    if output_dir:
        run.write(output_dir, name or Path(predictions_path).stem)
    return run


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--predictions", required=True)
    ap.add_argument("--subset", default="devset")
    ap.add_argument("--output-dir", default=None)
    ap.add_argument("--name", default=None)
    ap.add_argument("--json", action="store_true", help="print the summary as JSON")
    args = ap.parse_args()
    run = score(args.predictions, args.subset, args.output_dir, args.name)
    if args.json:
        print(json.dumps(run.summary.to_dict(), indent=2))
    else:
        print(f"[subset={args.subset}]")
        print(run.summary.render(args.name or Path(args.predictions).stem))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

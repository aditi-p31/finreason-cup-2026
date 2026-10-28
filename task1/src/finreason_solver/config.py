# SPDX-License-Identifier: Apache-2.0
"""Repository locations and split file names.

Every path is resolved relative to this file so the package works from any cwd.
No machine-specific path is built in; the defaults below are relative to the
package root (the directory holding ``run.sh``), and each can be overridden by
an environment variable:

``FINREASON_CUP_REPO``
    Checkout of https://github.com/The-FinAI/IEEE-bigdata-cup holding the
    Task 1 data (dataset version task1-v4) and the organisers' CLI.
    Default: ``../IEEE-bigdata-cup`` next to the package root.
``FINREASON_ARTIFACTS``
    Where solvers, the shape index, predictions and reports are read and
    written.  Default: ``artifacts/`` inside the package root.
``FINREASON_HOLDOUT_DEV``
    ``1`` derives solvers from the train split only (see below).
``FINREASON_HIDDEN_FORMS``
    ``1`` turns on the optional per-template forms for questions the shape
    index leaves unmatched (the same as ``--hidden-forms``).  They live in
    ``finreason_solver.hiddenforms``, which is not part of the default
    release.  Unset, the pipeline never imports that module.
``FINREASON_FINCHAIN_REPO``
    Optional checkout of https://github.com/mbzuai-nlp/finchain (commit
    146eaa8).  Recorded for reference only: FinChain is not a build input and
    nothing in the pipeline reads this path.  Default: ``../finchain``.
"""

from __future__ import annotations

import os
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
SOLUTION_DIR = PKG_DIR.parents[1]
FINREASON_DIR = SOLUTION_DIR.parent

CUP_REPO = Path(
    os.environ.get("FINREASON_CUP_REPO", FINREASON_DIR / "IEEE-bigdata-cup")
)
FINCHAIN_REPO = Path(
    os.environ.get("FINREASON_FINCHAIN_REPO", FINREASON_DIR / "finchain")
)

DATA_DIR = CUP_REPO / "public" / "task1" / "data"
DEV_DATA = DATA_DIR / "development"
TEST_DATA = DATA_DIR / "test"

TRAIN_QUESTIONS = DEV_DATA / "train_questions.jsonl"
TRAIN_GOLD = DEV_DATA / "train_gold.jsonl"
TRAIN_MANIFEST = DEV_DATA / "train_manifest.jsonl"
DEV_QUESTIONS = DEV_DATA / "dev_questions.jsonl"
DEV_GOLD = DEV_DATA / "dev_gold.jsonl"
DEV_MANIFEST = DEV_DATA / "dev_manifest.jsonl"
LB_QUESTIONS = DEV_DATA / "leaderboard_questions.jsonl"
LB_EXPECTED_IDS = DEV_DATA / "leaderboard_expected_ids.json"
TEST_QUESTIONS = TEST_DATA / "test_questions.jsonl"
TEST_EXPECTED_IDS = TEST_DATA / "test_expected_ids.json"

ARTIFACTS = Path(os.environ.get("FINREASON_ARTIFACTS", SOLUTION_DIR / "artifacts"))

# Set FINREASON_HOLDOUT_DEV=1 to derive solvers from the 2,900 train instances
# only, leaving the 290 dev cases genuinely unseen.  That turns `score-dev`
# into a held-out measurement instead of a fit-quality one.
HOLDOUT_DEV = os.environ.get("FINREASON_HOLDOUT_DEV") == "1"
# Off unless FINREASON_HIDDEN_FORMS=1 or --hidden-forms (see cli.py).
HIDDEN_FORMS = os.environ.get("FINREASON_HIDDEN_FORMS") == "1"
SOLVERS_JSON = ARTIFACTS / "solvers.json"
SHAPE_INDEX_JSON = ARTIFACTS / "shape_index.json"

PREDICTION_SCHEMA_VERSION = "finreason.task1.prediction/1.0.0"
DATASET_VERSION = "task1-v4"

# Global determinism knob: nothing in this pipeline draws randomness, but the
# induction search sorts candidate pools so that ties resolve identically on
# every run.
SEED = 20260904

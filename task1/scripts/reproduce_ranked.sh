#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Rebuild the ranked FinReason Task 1 test archive and check it byte for byte.
#
#   scripts/reproduce_ranked.sh          # from the shipped solver artifacts (seconds)
#   scripts/reproduce_ranked.sh --full   # rebuild every artifact first (hours)
#
# The ranked entry is the test submission accepted on 21 Oct 2026. It is the
# default pipeline plus the
# hidden-stratum forms (--hidden-forms). The script writes only into a new
# output directory: OUT if set (it must be empty or absent), else a fresh
# mktemp directory. ./artifacts and every other package file stay untouched.
#
# Default mode copies the three solver artifacts (solvers.json,
# shape_index.json, fallback_model.json) into OUT and runs
#   finreason_solver --hidden-forms package --split test
# --full instead runs `./run.sh --hidden-forms` with FINREASON_ARTIFACTS=OUT,
# which rebuilds the shape index, the solvers and the fallback model from the
# cup data before packaging (CPU-bound, about 2.5 hours).
#
# Prints "VERDICT: MATCH" and exits 0 only when both files hash to the ranked
# values below; otherwise prints "VERDICT: MISMATCH" and exits 1.
#
# Environment: PY and FINREASON_CUP_REPO as in run.sh. No network apart from
# the one-time venv setup; no language model is called.
set -euo pipefail
cd "$(dirname "$0")/.."

RANKED_PREDICTIONS_SHA256=3f0bec6f039e66b49365af039ab0ab41902c3274dab43b8d02fb3c6a16c4a2d4
RANKED_ZIP_SHA256=b786d1e5b8b7284b762e8dbbd2248692cfe4af87348d69f1eb8f464a85dc0991

MODE=default
case "${1:-}" in
  "") ;;
  --full) MODE=full ;;
  -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
  *) echo "unknown argument: $1 (use --full or nothing)" >&2; exit 2 ;;
esac

if [ ! -f src/finreason_solver/hiddenforms/routes.json ]; then
  echo "this bundle has no hidden-stratum forms (src/finreason_solver/hiddenforms/);" >&2
  echo "the ranked archive needs the bundle built with --with-hidden-forms" >&2
  exit 2
fi

OUT="${OUT:-$(mktemp -d "${TMPDIR:-/tmp}/finreason-ranked.XXXXXX")}"
mkdir -p "$OUT"
if [ -n "$(ls -A "$OUT")" ]; then
  echo "OUT=$OUT is not empty; give a new or empty directory" >&2
  exit 2
fi
OUT="$(cd "$OUT" && pwd)"
echo "mode: $MODE"
echo "output directory: $OUT"

if [ "$MODE" = full ]; then
  FINREASON_ARTIFACTS="$OUT" ./run.sh --hidden-forms
  PY="${PY:-.venv/bin/python}"
else
  PY="${PY:-.venv/bin/python}"
  if [ ! -x "$PY" ]; then
    echo "creating .venv (python 3.11)" >&2
    if command -v uv >/dev/null 2>&1; then
      uv venv --python 3.11 .venv
      uv pip install --python .venv/bin/python -r requirements.lock.txt
    else
      python3.11 -m venv .venv
      .venv/bin/python -m pip install -r requirements.lock.txt
    fi
  fi
  cp artifacts/solvers.json artifacts/shape_index.json artifacts/fallback_model.json "$OUT"/
  FINREASON_ARTIFACTS="$OUT" PYTHONPATH="src:${PYTHONPATH:-}" \
    "$PY" -m finreason_solver --hidden-forms package --split test
fi

sha() { "$PY" -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$1"; }

status=0
check() {  # file expected label
  if [ ! -f "$1" ]; then
    echo "MISSING  $2  $1"; status=1; return
  fi
  got="$(sha "$1")"
  if [ "$got" = "$2" ]; then
    echo "OK       $got  $3"
  else
    echo "DIFFERS  $got  $3 (expected $2)"; status=1
  fi
}
check "$OUT/test_predictions.jsonl" "$RANKED_PREDICTIONS_SHA256" test_predictions.jsonl
check "$OUT/test_submission.zip" "$RANKED_ZIP_SHA256" test_submission.zip
if [ -f accepted_20261021/test_predictions.jsonl ]; then
  if cmp -s "$OUT/test_predictions.jsonl" accepted_20261021/test_predictions.jsonl; then
    echo "OK       byte-identical to accepted_20261021/test_predictions.jsonl"
  else
    echo "DIFFERS  from accepted_20261021/test_predictions.jsonl"; status=1
  fi
fi

if [ "$status" -eq 0 ]; then
  echo "VERDICT: MATCH (ranked Task 1 test archive reproduced: $OUT/test_submission.zip)"
else
  echo "VERDICT: MISMATCH"
fi
exit "$status"

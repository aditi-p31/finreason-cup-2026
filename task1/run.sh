#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Regenerate every artifact from scratch: shape index, solvers, fallback model,
# dev score under the organisers' scorer, and both submission archives.
#
#   ./run.sh                      # extra arguments go to `finreason_solver all`
#
# Environment (all optional):
#   PY                   python to use (default: .venv/bin/python, created on
#                        first run with uv, or with python3.11 -m venv if uv is
#                        not installed)
#   FINREASON_CUP_REPO   cup checkout (default: ../IEEE-bigdata-cup)
#   FINREASON_ARTIFACTS  output directory (default: ./artifacts)
#
# Exit status: 0 only when every stage succeeded. The first failing stage
# (build-index, build-solvers, build-fallback, score-dev, package) stops the
# run, and its non-zero exit code is this script's exit code.
#
# The pipeline itself calls no network service and no language model. The
# only network access is the one-time venv setup, which installs the test
# dependencies pinned in requirements.lock.txt.
set -euo pipefail
cd "$(dirname "$0")"

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

export PYTHONPATH="src:${PYTHONPATH:-}"
"$PY" -m finreason_solver all "$@"

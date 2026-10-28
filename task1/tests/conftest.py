# SPDX-License-Identifier: Apache-2.0
"""Put both our package and the organisers' kit on the import path."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from finreason_solver import config  # noqa: E402

if str(config.CUP_REPO) not in sys.path:
    sys.path.insert(0, str(config.CUP_REPO))

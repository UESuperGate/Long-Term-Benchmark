#!/usr/bin/env python3
"""Run the shared API23 ArkTS scorer for Reading Lists."""

from __future__ import annotations

import os
import sys
from pathlib import Path


MIGRATION = Path(__file__).resolve().parents[1]
TOOL = MIGRATION.parent / "tools/run_arkts_state_transition.py"
os.execv(sys.executable, [sys.executable, str(TOOL), "--migration", str(MIGRATION), *sys.argv[1:]])

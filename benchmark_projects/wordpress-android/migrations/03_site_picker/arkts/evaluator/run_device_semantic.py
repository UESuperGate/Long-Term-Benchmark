#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path


MIGRATION = Path(__file__).resolve().parents[2]
TOOL = MIGRATION.parent / "tools/run_arkts_state_transition.py"
os.execv(sys.executable, [sys.executable, str(TOOL), "--migration", str(MIGRATION), *sys.argv[1:]])

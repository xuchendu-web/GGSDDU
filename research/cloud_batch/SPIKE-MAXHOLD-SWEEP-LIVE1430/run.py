#!/usr/bin/env python3
"""Entrypoint for SPIKE-MAXHOLD-SWEEP-LIVE1430 cloud batch."""
from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).resolve().parent / "engine" / "run_maxhold_sweep.py"), run_name="__main__")

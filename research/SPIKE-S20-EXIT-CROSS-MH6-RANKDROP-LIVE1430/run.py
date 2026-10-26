#!/usr/bin/env python3
"""Entrypoint for SPIKE-S20-EXIT-CROSS-MH6-RANKDROP-LIVE1430."""
from pathlib import Path
import runpy

runpy.run_path(
    str(Path(__file__).resolve().parent / "engine" / "run_exit_cross.py"),
    run_name="__main__",
)

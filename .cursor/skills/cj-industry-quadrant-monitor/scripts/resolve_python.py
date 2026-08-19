#!/usr/bin/env python3
"""Print the interpreter saved by bootstrap.ps1; never discovers a new one."""
import json
from pathlib import Path

state = Path(__file__).resolve().parents[1] / ".iqm-runtime.json"
try:
    python = Path(json.loads(state.read_text(encoding="utf-8-sig"))["python"])
except Exception as e:
    raise SystemExit("No saved runtime. Run .\\bootstrap.ps1 first. ({})".format(e))
if not python.is_file():
    raise SystemExit("Saved Python no longer exists: {}. Run .\\bootstrap.ps1 -Reconfigure.".format(python))
print(python)

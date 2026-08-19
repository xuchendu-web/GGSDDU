#!/usr/bin/env python3
"""Configure CJPY interactively. Token input is hidden and never logged."""
import getpass
from pathlib import Path
import cjpy

token = getpass.getpass("CJPY token (input hidden): ")
if not token:
    raise SystemExit("Token cannot be empty.")
cjpy.set_token(token, persist=True)
token = ""
print("CJPY token saved to {}".format(Path.home() / ".cjpy" / "config.json"))

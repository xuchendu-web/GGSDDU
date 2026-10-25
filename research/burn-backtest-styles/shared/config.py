"""Frozen toy-rule parameters shared by all three engine styles."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PANEL_CSV = DATA_DIR / "synthetic_panel.csv"

SEED = 42
N_SYMBOLS = 8
N_TRADING_DAYS = 260  # ~1y of business days

TOP_K = 3
MOM_LOOKBACK_DAYS = 60  # ~12 weeks
MA_WINDOW = 20
BREADTH_MIN = 0.45

# Weekly rebalance on last observation in each Fri-labeled week (pandas 'W-FRI').
RESAMPLE_RULE = "W-FRI"

SYMBOL_PREFIX = "SYN"

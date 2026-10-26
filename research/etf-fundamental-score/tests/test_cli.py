import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_cli_scores_fixture(tmp_path):
    out = tmp_path / "scores.csv"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "etf_fundamental_score.cli",
            "-i",
            str(ROOT / "fixtures" / "universe_sample.csv"),
            "-c",
            str(ROOT / "config.yaml"),
            "-o",
            str(out),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert "composite_score" in text
    assert "510300.SH" in text

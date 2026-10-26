import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_batch_cli_manifest(tmp_path):
    out_dir = tmp_path / "out"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "etf_fundamental_score.cli",
            "batch",
            "-m",
            str(ROOT / "fixtures" / "batch_manifest.csv"),
            "-c",
            str(ROOT / "config.yaml"),
            "-o",
            str(out_dir),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert (out_dir / "universe_sample_scores.csv").is_file()
    assert (out_dir / "all_scores.csv").is_file()

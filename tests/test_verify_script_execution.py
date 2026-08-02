from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_verify_phase1_runs_as_direct_script() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_phase1.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads(completed.stdout)
    assert report["controlled_reference_masters"] == 14
    assert report["errors"] == []

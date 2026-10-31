"""E0: the evidence ledgers (parameters and capabilities) must stay consistent."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _run(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed scripts, no shell
        [sys.executable, str(ROOT / "scripts" / script), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_param_ledger_is_consistent() -> None:
    result = _run("param_gate.py")
    assert result.returncode == 0, result.stdout + result.stderr


def test_capability_ledger_is_consistent() -> None:
    result = _run("capability_gate.py", "--check")
    assert result.returncode == 0, result.stdout + result.stderr

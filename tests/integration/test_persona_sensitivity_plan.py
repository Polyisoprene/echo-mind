"""P6e: the live sensitivity runner must produce a correct, cost-free plan."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_sensitivity_dry_run_plan(tmp_path: Path) -> None:
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [
            sys.executable,
            str(ROOT / "scripts" / "persona_sensitivity.py"),
            "--config",
            str(tmp_path / "missing.json"),
            "--dry-run",
            "--scenarios",
            "4",
            "--out",
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    reports = sorted(tmp_path.glob("persona_sensitivity_*.json"))
    assert reports, "dry-run must still write the plan"
    plan = json.loads(reports[-1].read_text(encoding="utf-8"))

    assert plan["status"] == "dry_run"
    scenario_count = sum(plan["scenarios"].values())
    assert plan["generations"] == scenario_count * 2
    assert plan["judgements"] == scenario_count
    assert plan["self_judged"] is True

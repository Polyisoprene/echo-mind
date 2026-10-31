"""P6e: the persona evaluation harness must stay runnable and non-vacuous."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _run(out: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed argv, no shell
        [
            sys.executable,
            str(ROOT / "scripts" / "eval_persona.py"),
            "--suite",
            "all",
            "--days",
            "30",
            "--out",
            str(out),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_offline_eval_harness_reports_expected_metrics(tmp_path: Path) -> None:
    result = _run(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr

    reports = sorted(tmp_path.glob("persona_eval_*.json"))
    assert reports, "the harness must write a report"
    report = json.loads(reports[-1].read_text(encoding="utf-8"))

    stability = report["suites"]["stability"]
    assert 0 < stability["net_change"] <= 30 * 0.0134
    assert stability["saturated"] is False

    assert report["suites"]["affect"]["accuracy"] >= 0.8
    recall = report["suites"]["recall"]
    assert recall["direct_recall"] > recall["paraphrase_recall"]
    assert report["suites"]["sensitivity"]["status"] == "not_run"

"""Regression: the judge prompt must include the model response, not `{}`."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _module() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "scripts" / "eval_longmemeval_qa.py"
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("eval_longmemeval_qa_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_judge_prompt_contains_response() -> None:
    module = _module()
    question = {
        "question_id": "q1", "question_type": "single-session-user",
        "question": "What degree?", "answer": "Business Administration",
    }
    prompt = module._judge_prompt(question, "Business Administration")
    assert "Model Response: Business Administration" in prompt
    assert "Model Response: {}" not in prompt


def test_cot_prompt_uses_official_step_by_step() -> None:
    module = _module()
    plain = module._answer_prompt("q", "d", ["history"], False)
    cot = module._answer_prompt("q", "d", ["history"], True)
    assert "step by step" not in plain.lower()
    assert "step by step" in cot.lower()
    assert "Answer (step by step):" in cot

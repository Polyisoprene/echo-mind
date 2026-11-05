"""Regression: extraction of one JSON object from messy LLM output.

The previous implementation used a greedy `\\{[\\s\\S]*\\}` regex, which spanned
from the first `{` to the last `}`, so any trailing prose or a second object
made the whole payload unparseable. These tests pin the cases that used to fail.
"""

from __future__ import annotations

import pytest

from echomind.domain.json_extract import extract_json_object


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"cards": []}', {"cards": []}),
        ("```json\n{\"cards\": []}\n```", {"cards": []}),
        ('好的，我提炼如下：\n{"cards": []}\n以上是全部。', {"cards": []}),
        ('{"cards": []}\n顺便说一句我也很开心。', {"cards": []}),
        ('{"cards": [{"summary": "她说{好开心}"}]}', {"cards": [{"summary": "她说{好开心}"}]}),
        ('{"a": "he said \\"hi\\""}', {"a": 'he said "hi"'}),
        ('{"a": {"b": {"c": 1}}}', {"a": {"b": {"c": 1}}}),
    ],
)
def test_extracts_object_from_wrapped_output(raw: str, expected: dict[str, object]) -> None:
    assert extract_json_object(raw) == expected


def test_returns_first_parseable_object_when_several_present() -> None:
    """A reasoning trace object followed by the real payload must not merge them."""
    raw = '{"think": 1}\n{"cards": []}'
    assert extract_json_object(raw) == {"think": 1}


def test_skips_unbalanced_brace_before_payload() -> None:
    """Prose that opens a brace never closes it; the real object must still be found."""
    raw = '我想 { 然后输出 {"cards": []}'
    assert extract_json_object(raw) == {"cards": []}


def test_skips_invalid_object_before_payload() -> None:
    raw = '{"bad": }\n{"good": 1}'
    assert extract_json_object(raw) == {"good": 1}


def test_skips_nested_brace_wrappers() -> None:
    assert extract_json_object('{{{ "a": 1 }}}') == {"a": 1}


@pytest.mark.parametrize("raw", ["", "没有 JSON 对象", "[1, 2, 3]", "{未闭合"])
def test_returns_none_when_absent(raw: str) -> None:
    assert extract_json_object(raw) is None


def test_non_dict_json_is_rejected() -> None:
    """Only objects are valid payloads; bare arrays must not be returned."""
    assert extract_json_object("[1, 2]") is None

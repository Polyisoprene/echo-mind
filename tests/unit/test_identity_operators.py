"""Operator ids are editable from the console, never empty, and migrate off the legacy key."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from echomind.mind.naming import BotNaming, set_bot_naming
from echomind.web.identity_service import IdentityConfigService


def _cfg(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "config.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_read_falls_back_to_legacy_owner_key(tmp_path: Path) -> None:
    path = _cfg(tmp_path, {"skills": {"affinity": {"ownerQq": "10001001"}}})
    assert IdentityConfigService(path).read()["operators"] == ["10001001"]


def test_save_writes_operator_ids_and_drops_legacy(tmp_path: Path) -> None:
    path = _cfg(tmp_path, {"skills": {"affinity": {"ownerQq": "1"}}})
    try:
        service = IdentityConfigService(path)
        service.save({"operators": ["2", "3"]})
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert raw["operatorIds"] == ["2", "3"]
        assert "ownerQq" not in raw["skills"]["affinity"]
        assert service.read()["operators"] == ["2", "3"]
    finally:
        set_bot_naming(BotNaming())


def test_empty_operators_are_rejected(tmp_path: Path) -> None:
    path = _cfg(tmp_path, {"operatorIds": ["1"]})
    with pytest.raises(ValueError):
        IdentityConfigService(path).save({"operators": []})


def test_hot_apply_updates_runtime_operators() -> None:
    from echomind.adapters.onebot.identity_hot_apply import apply_identity

    class _Runtime:
        _operator_ids: tuple[str, ...] = ()
        _groups: frozenset[str] = frozenset()
        _priv_users: frozenset[str] = frozenset()
        _self_id: str = ""
        _bot_names: tuple[str, ...] = ()

    runtime = _Runtime()
    apply_identity(runtime, operators=("9",))
    assert runtime._operator_ids == ("9",)

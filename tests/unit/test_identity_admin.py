"""Stage 29 A5: identity edits persist to config.json and apply live."""

from __future__ import annotations

import json
from pathlib import Path

from echomind.adapters.onebot.identity_hot_apply import apply_identity
from echomind.mind.naming import BotNaming, bot_naming, set_bot_naming
from echomind.web.identity_service import IdentityConfigService


def test_save_persists_and_applies_naming(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"persona": {"botName": "回音"}}), encoding="utf-8")
    service = IdentityConfigService(cfg)

    try:
        saved = service.save(
            {"bot_name": "星野", "keywords": ["星野", "小星"], "self_qq": "10003003",
             "groups": ["10002002"], "private": ["10001001"], "default_group": "group:10002002"}
        )
        assert saved["bot_name"] == "星野" and "小星" in saved["keywords"]
        assert bot_naming().label() == "星野"
        raw = json.loads(cfg.read_text(encoding="utf-8"))
        assert raw["persona"]["botName"] == "星野"
        assert raw["store"]["keywords"] == ["星野", "小星"]
        assert raw["selfQq"] == "10003003"
        assert raw["allow"]["groups"] == ["10002002"]
    finally:
        set_bot_naming(BotNaming())


def test_read_reports_current_identity(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    payload = {"persona": {"botName": "回音"}, "store": {"keywords": ["回音", "尾尾"]}}
    cfg.write_text(json.dumps(payload), encoding="utf-8")
    got = IdentityConfigService(cfg).read()
    assert got["bot_name"] == "回音" and got["keywords"] == ["回音", "尾尾"]


def test_hot_apply_updates_runtime_filters() -> None:
    class _Runtime:
        _groups: frozenset[str] = frozenset()
        _priv_users: frozenset[str] = frozenset()
        _self_id: str = ""
        _bot_names: tuple[str, ...] = ()

    runtime = _Runtime()
    apply_identity(runtime, bot_name="星野", groups=("1",), private=("2",), self_id="3")
    assert runtime._groups == frozenset({"1"})
    assert runtime._priv_users == frozenset({"2"})
    assert runtime._self_id == "3"
    assert "星野" in runtime._bot_names

"""Read, write, toggle, and delete skills and their configurations from the console."""

from __future__ import annotations

from typing import Any

from echomind.core.bootstrap import EchoMindContainer
from echomind.domain.models import SkillConfigField
from echomind.domain.ports import IConfigurableTool

STATE_SKILL_KEY = "__skill_state__"
DEFAULT_TOOL_FIELDS: tuple[SkillConfigField, ...] = (
    SkillConfigField(
        key="custom_note",
        label="备注 / 附加说明",
        kind="text",
        placeholder="可选：为该技能记录运营备注或使用说明",
    ),
)


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "…" + value[-4:]


def _tool_fields(tool: Any) -> list[dict[str, Any]]:
    if isinstance(tool, IConfigurableTool):
        return [f.model_dump() for f in tool.config_fields()]
    return [f.model_dump() for f in DEFAULT_TOOL_FIELDS]


class SkillConfigService:
    """Expose per-skill config fields, masked values, and enable/disable/delete lifecycle."""

    def __init__(self, container: EchoMindContainer) -> None:
        self._c = container

    async def _sync_feiyu_backend(self) -> None:
        store = self._c.skill_config_store
        vb = self._c.voice_backend
        if store is None or vb is None:
            return
        fv = await store.get_skill_config("feiyu_voice")
        if fv:
            vb.configure(
                base_url=fv.get("base_url", ""),
                api_key=fv.get("api_key", ""),
                default_style=fv.get("style", ""),
            )

    async def sync_states(self) -> None:
        """Load persisted enable/delete states and runtime skill configs from SQLite."""
        store = self._c.skill_config_store
        if store is None:
            return
        raw = await store.get_skill_config(STATE_SKILL_KEY)
        for name in self._c.registry.tools:
            en_val = raw.get(f"enabled:{name}")
            del_val = raw.get(f"deleted:{name}")
            self._c.registry.set_tool_state(
                name,
                enabled=(en_val != "0") if en_val is not None else True,
                deleted=(del_val == "1") if del_val is not None else False,
            )
        await self._sync_feiyu_backend()

    def _declared(self) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for tool in self._c.registry.tools.values():
            key = str(getattr(tool, "config_key", "") or getattr(tool, "name", ""))
            if not key or key in grouped:
                continue
            grouped[key] = _tool_fields(tool)
        return grouped

    async def list_configs(self) -> list[dict[str, Any]]:
        """Return every skill config group with its current (masked) values."""
        await self.sync_states()
        declared = self._declared()
        store = self._c.skill_config_store
        result: list[dict[str, Any]] = []
        for key, fields in declared.items():
            values = await store.get_skill_config(key) if store is not None else {}
            shown = {
                f["key"]: (
                    _mask(values.get(f["key"], "")) if f.get("secret") else values.get(f["key"], "")
                )
                for f in fields
            }
            result.append({"skill": key, "fields": fields, "values": shown})
        return result

    async def save(self, skill: str, values: dict[str, str]) -> dict[str, Any]:
        """Persist provided values, ignoring masked placeholders echoed back."""
        store = self._c.skill_config_store
        if store is None:
            return {"ok": False, "reason": "配置存储不可用"}
        declared = {f["key"] for f in self._declared().get(skill, [])}
        patch = {
            k: v for k, v in values.items() if k in declared and "…" not in v and set(v) != {"*"}
        }
        await store.set_skill_config(skill, patch)
        if skill == "feiyu_voice":
            await self._sync_feiyu_backend()
        return {"ok": True, "skill": skill, "saved_keys": sorted(patch)}

    async def toggle_tool(self, name: str) -> dict[str, Any]:
        """Flip enabled/disabled state for one skill tool and persist it."""
        await self.sync_states()
        new_enabled = not self._c.registry.is_tool_enabled(name)
        self._c.registry.set_tool_state(name, enabled=new_enabled)
        if self._c.skill_config_store is not None:
            await self._c.skill_config_store.set_skill_config(
                STATE_SKILL_KEY, {f"enabled:{name}": "1" if new_enabled else "0"}
            )
        return {"ok": True, "name": name, "enabled": new_enabled}

    async def delete_tool(self, name: str) -> dict[str, Any]:
        """Mark one skill tool as deleted and persist it."""
        await self.sync_states()
        self._c.registry.set_tool_state(name, deleted=True)
        if self._c.skill_config_store is not None:
            await self._c.skill_config_store.set_skill_config(
                STATE_SKILL_KEY, {f"deleted:{name}": "1"}
            )
        return {"ok": True, "name": name, "deleted": True}

    async def restore_deleted(self) -> dict[str, Any]:
        """Restore all previously deleted skill tools."""
        await self.sync_states()
        deleted = list(self._c.registry.deleted_tools)
        for name in deleted:
            self._c.registry.set_tool_state(name, deleted=False)
        if self._c.skill_config_store is not None and deleted:
            await self._c.skill_config_store.set_skill_config(
                STATE_SKILL_KEY, {f"deleted:{name}": "0" for name in deleted}
            )
        return {"ok": True, "restored": deleted}

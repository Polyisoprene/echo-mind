"""M4.1 Microkernel 5-Slot Typed Extension Registry enforcing Open/Closed Principle."""

from __future__ import annotations

from typing import Any

from echomind.domain.ports import (
    ICognitiveFacet,
    IConfigurableTool,
    IInspectorPanel,
    IPerceptEnricher,
    IProactiveProposer,
    IToolExtension,
)


def _require_protocol(obj: Any, proto: Any, slot_name: str) -> None:
    if not isinstance(obj, proto):
        raise TypeError(f"{type(obj).__name__} does not satisfy {slot_name} protocol")


class ExtensionRegistry:
    """5-Slot strongly-typed plugin registry with runtime enable/disable/delete support."""

    def __init__(self) -> None:
        self._sensors: list[IPerceptEnricher] = []
        self._tools: dict[str, IToolExtension] = {}
        self._disabled_tools: set[str] = set()
        self._deleted_tools: set[str] = set()
        self._facets: dict[str, ICognitiveFacet] = {}
        self._proposers: list[IProactiveProposer] = []
        self._panels: dict[str, IInspectorPanel] = {}

    @property
    def sensors(self) -> tuple[IPerceptEnricher, ...]:
        return tuple(self._sensors)

    @property
    def tools(self) -> dict[str, IToolExtension]:
        return dict(self._tools)

    @property
    def deleted_tools(self) -> frozenset[str]:
        return frozenset(self._deleted_tools)

    @property
    def facets(self) -> tuple[ICognitiveFacet, ...]:
        return tuple(self._facets.values())

    @property
    def proposers(self) -> tuple[IProactiveProposer, ...]:
        return tuple(self._proposers)

    @property
    def panels(self) -> tuple[IInspectorPanel, ...]:
        return tuple(self._panels.values())

    def register_sensor(self, sensor: IPerceptEnricher) -> None:
        _require_protocol(sensor, IPerceptEnricher, "Slot-1 PerceptEnricher")
        self._sensors.append(sensor)

    def register_tool(self, tool: IToolExtension) -> None:
        _require_protocol(tool, IToolExtension, "Slot-2 ToolExtension")
        self._tools[tool.name] = tool

    def register_facet(self, facet: ICognitiveFacet) -> None:
        _require_protocol(facet, ICognitiveFacet, "Slot-3 CognitiveFacet")
        self._facets[facet.facet_id] = facet

    def register_proposer(self, proposer: IProactiveProposer) -> None:
        _require_protocol(proposer, IProactiveProposer, "Slot-4 ProactiveProposer")
        self._proposers.append(proposer)

    def register_panel(self, panel: IInspectorPanel) -> None:
        _require_protocol(panel, IInspectorPanel, "Slot-5 InspectorPanel")
        self._panels[panel.panel_id] = panel

    def is_tool_enabled(self, name: str) -> bool:
        return name not in self._disabled_tools and name not in self._deleted_tools

    def set_tool_state(
        self, name: str, *, enabled: bool | None = None, deleted: bool | None = None
    ) -> None:
        if enabled is not None:
            if enabled:
                self._disabled_tools.discard(name)
            else:
                self._disabled_tools.add(name)
        if deleted is not None:
            if deleted:
                self._deleted_tools.add(name)
            else:
                self._deleted_tools.discard(name)

    def export_skill_catalog(self) -> list[dict[str, Any]]:
        """Group non-deleted tools by category with enabled status and config fields."""
        groups: dict[str, list[dict[str, Any]]] = {}
        for tool in self._tools.values():
            if tool.name in self._deleted_tools:
                continue
            config_key = getattr(tool, "config_key", tool.name)
            fields = (
                [f.model_dump() for f in tool.config_fields()]
                if isinstance(tool, IConfigurableTool)
                else []
            )
            groups.setdefault(tool.category, []).append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "enabled": tool.name not in self._disabled_tools,
                    "parameters": tool.parameters_schema(),
                    "config_key": config_key,
                    "config_fields": fields,
                }
            )
        return [
            {"category": cat, "tools": items}
            for cat, items in sorted(groups.items(), key=lambda kv: kv[0])
        ]

    def export_openai_tools(
        self, selected_names: tuple[str, ...] = ()
    ) -> list[dict[str, Any]]:
        """Export enabled tools in OpenAI format, optionally filtered by Ashby reagent selection."""
        enabled_tools = [t for t in self._tools.values() if self.is_tool_enabled(t.name)]
        allow = frozenset(selected_names)
        chosen = [t for t in enabled_tools if t.name in allow] if allow else enabled_tools
        target = chosen if chosen else enabled_tools
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters_schema(),
                },
            }
            for t in target
        ]

    async def execute_tool(self, name: str, chat_key: str, args: dict[str, Any]) -> str:
        """Dispatch an LLM tool call by name; reject unknown, disabled, or failing tools safely."""
        tool = self._tools.get(name)
        if tool is None or name in self._deleted_tools:
            return f"未找到工具: {name}"
        if name in self._disabled_tools:
            return f"技能 {name} 已在控制台被禁用"
        try:
            return await tool.execute(chat_key, args)
        except Exception as exc:
            detail = str(exc).strip() or type(exc).__name__
            return f"工具 {name} 执行失败: {detail}"

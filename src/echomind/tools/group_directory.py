"""Group directory tool for explicit cross-chat target resolution."""

from __future__ import annotations

import json
from typing import Any

from echomind.domain.group_ports import IGroupDirectory


class ListGroupsTool:
    """List group conversations so the model can resolve a target instead of guessing."""

    category = "社交互动"

    def __init__(self, directory: IGroupDirectory) -> None:
        self._directory = directory

    @property
    def name(self) -> str:
        return "list_groups"

    @property
    def description(self) -> str:
        return "列出当前账号加入的群（群号+群名），用于确认跨会话发送目标，避免猜群名。"

    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, chat_key: str, args: dict[str, Any]) -> str:
        groups = await self._directory.list_groups()
        return json.dumps({"groups": list(groups)}, ensure_ascii=False)

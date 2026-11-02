"""list_groups exposes real group ids/names for cross-chat targeting."""

from __future__ import annotations

from echomind.tools.group_directory import ListGroupsTool


class _Directory:
    async def list_groups(self) -> tuple[dict[str, object], ...]:
        return ({"group_id": "10002002", "group_name": "测试群"},)


async def test_list_groups_returns_id_and_name() -> None:
    out = await ListGroupsTool(_Directory()).execute("private:1", {})
    assert "10002002" in out
    assert "测试群" in out

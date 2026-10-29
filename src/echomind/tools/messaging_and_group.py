"""M4.1 Stateless Messaging & Group Roster Tools satisfying IToolExtension (ISP & DIP)."""

from __future__ import annotations

import json
import time
from typing import Any

from echomind.domain.models import SocialBondProfile
from echomind.domain.ports import IGroupRosterReader, IMessageSender

PUNCT_END = ("，", "。", "！", "？", "～", "~", "…", ",", ".", "!", "?")


def _merge_clauses(parts: tuple[str, ...]) -> tuple[str, ...]:
    """Combine split clauses into a single natural sentence without dropping tail clauses."""
    if len(parts) <= 1:
        return parts
    pieces: list[str] = []
    for idx, part in enumerate(parts):
        pieces.append(part)
        if idx + 1 < len(parts) and not part.endswith(PUNCT_END):
            pieces.append("，")
    return ("".join(pieces),)


class SendMessageTool:
    """Send 1..3 short natural chat messages with optional quote or @mention."""

    category = "社交互动"

    def __init__(self, sender: IMessageSender) -> None:
        self._sender = sender

    @property
    def name(self) -> str:
        return "send_message"

    @property
    def description(self) -> str:
        return (
            "发送文字回复（把想说的话合并成 1 句自然口语发出，支持引用 reply_to 或艾特 at_user）。"
        )

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "messages": {"type": "array", "items": {"type": "string"}},
                "reply_to": {
                    "type": "string",
                    "description": "可选：要引用的消息编号（即消息开头的 #数字，去掉 #；勿填QQ号）",
                },
                "at_user": {
                    "type": "string",
                    "description": "可选：要艾特(@)的群友数字 QQ 号",
                },
            },
            "required": ["messages"],
        }

    async def execute(self, chat_key: str, args: dict[str, Any]) -> str:
        raw_msgs = args.get("messages", [])
        if isinstance(raw_msgs, str):
            raw_msgs = [raw_msgs]
        raw_tuple = tuple(str(m).strip() for m in raw_msgs if str(m).strip())
        if not raw_tuple:
            return "未发送：消息内容为空"
        clean_tuple = _merge_clauses(raw_tuple)
        reply_to = str(args.get("reply_to", "")).strip() or None
        at_user = str(args.get("at_user", "")).strip() or None
        mids = await self._sender.send_text(
            chat_key, clean_tuple, reply_to_mid=reply_to, at_user_id=at_user
        )
        return json.dumps({"ok": True, "sent_count": len(mids), "message_ids": list(mids)})


STICKER_COOLDOWN_MS = 30_000


class SendStickerTool:
    """Send a sticker by sticker_id from the rotated sticker pool."""

    category = "社交互动"

    def __init__(self, sender: IMessageSender, *, cooldown_ms: int = STICKER_COOLDOWN_MS) -> None:
        self._sender = sender
        self._cooldown_ms = cooldown_ms
        self._last_sent: dict[str, int] = {}

    def _remaining_ms(self, chat_key: str, now_ms: int) -> int:
        last = self._last_sent.get(chat_key, 0)
        return max(0, self._cooldown_ms - (now_ms - last))

    @property
    def name(self) -> str:
        return "send_sticker"

    @property
    def description(self) -> str:
        return "发送一张表情包（传入【可用表情包】列表中的 sticker_id）。"

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "sticker_id": {"type": "string"},
                "reply_to": {"type": "string"},
            },
            "required": ["sticker_id"],
        }

    async def execute(self, chat_key: str, args: dict[str, Any]) -> str:
        sid = str(args.get("sticker_id", "")).strip()
        if not sid:
            return "未发送：缺少 sticker_id"
        reply_to = str(args.get("reply_to", "")).strip() or None
        now_ms = int(time.time() * 1000)
        remaining = self._remaining_ms(chat_key, now_ms)
        if remaining > 0:
            return f"刚发过表情包了，{remaining // 1000 + 1} 秒后再发（别刷屏）"
        mid = await self._sender.send_sticker(chat_key, sid, reply_to_mid=reply_to)
        if not mid:
            return f"发送表情失败：未找到 {sid}"
        self._last_sent[chat_key] = now_ms
        return json.dumps({"ok": True, "sticker_id": sid, "message_id": mid})


class SendPokeTool:
    """Poke a group member or friend."""

    category = "社交互动"

    def __init__(self, sender: IMessageSender) -> None:
        self._sender = sender

    @property
    def name(self) -> str:
        return "send_poke"

    @property
    def description(self) -> str:
        return "拍一拍指定群友或好友（传入对方 QQ 号 user_id）。"

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"user_id": {"type": "string"}},
            "required": ["user_id"],
        }

    async def execute(self, chat_key: str, args: dict[str, Any]) -> str:
        uid = str(args.get("user_id", "")).strip()
        if not uid.isdigit():
            return "拍一拍失败：user_id 必须是数字 QQ 号"
        await self._sender.send_poke(chat_key, uid)
        return json.dumps({"ok": True, "poked_user_id": uid})


def _filter_members(
    members: tuple[SocialBondProfile, ...], keyword: str
) -> tuple[SocialBondProfile, ...]:
    if not keyword:
        return members
    kw = keyword.lower()
    return tuple(m for m in members if kw in m.user_name.lower() or kw in m.user_id.lower())


def _role_labels(members: tuple[SocialBondProfile, ...], role: str) -> list[str]:
    return [f"{m.user_name}(QQ:{m.user_id})" for m in members if m.group_role == role]


def _format_roster(
    members: tuple[SocialBondProfile, ...],
    *,
    page: int = 1,
    page_size: int = 100,
    keyword: str = "",
) -> str:
    filtered = _filter_members(members, keyword)
    owners = _role_labels(filtered, "owner")
    admins = _role_labels(filtered, "admin")
    others = _role_labels(filtered, "member")
    size = max(10, min(page_size, 200))
    total_pages = max(1, (len(others) + size - 1) // size)
    cur_page = max(1, min(page, total_pages))
    page_items = others[(cur_page - 1) * size : cur_page * size]
    lines = [
        f"👑群主: {', '.join(owners) or '无'}",
        f"🛡️管理员: {', '.join(admins) or '无'}",
        f"👥普通群员(共{len(others)}人，第{cur_page}/{total_pages}页): "
        f"{', '.join(page_items) or '无'}",
    ]
    if cur_page < total_pages:
        lines.append(f"💡 还有后续群员，可传 page={cur_page + 1} 翻页或传 keyword 搜索。")
    return "\n".join(lines)


class GetGroupMembersTool:
    """Authoritative group roster lookup tool with pagination and keyword filtering."""

    category = "社交互动"

    def __init__(self, roster_reader: IGroupRosterReader) -> None:
        self._reader = roster_reader

    @property
    def name(self) -> str:
        return "get_group_members"

    @property
    def description(self) -> str:
        return (
            "查询当前 QQ 群真实群主、管理员与群成员名单（支持 page 翻页与 keyword 搜索名字/QQ）。"
        )

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "page": {"type": "integer", "description": "页码（从 1 开始，默认每页 100 人）"},
                "page_size": {"type": "integer", "description": "每页人数（默认 100，最大 200）"},
                "keyword": {"type": "string", "description": "按昵称/群名片或 QQ 号关键词过滤"},
            },
        }

    async def execute(self, chat_key: str, args: dict[str, Any]) -> str:
        if not chat_key.startswith("group:"):
            return "当前是私聊场景，无群成员列表。"
        gid = chat_key.split(":", 1)[1]
        try:
            page = int(args.get("page", 1) or 1)
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = int(args.get("page_size", 100) or 100)
        except (TypeError, ValueError):
            page_size = 100
        keyword = str(args.get("keyword", "") or "").strip()
        members = await self._reader.get_group_members(gid)
        return _format_roster(members, page=page, page_size=page_size, keyword=keyword)

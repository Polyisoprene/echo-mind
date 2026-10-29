"""Member identity & impression memory tool (memory_append) bound to QQ user_id."""

from __future__ import annotations

import json
from typing import Any

from echomind.domain.models import SemanticFact, SocialBondProfile
from echomind.domain.ports import IMemoryReader, IMemoryWriter


class RememberMemberTool:
    """Persist a permanent member identity, alias, or impression bound to their QQ number."""

    category = "社交互动"

    def __init__(self, reader: IMemoryReader, writer: IMemoryWriter) -> None:
        self._reader = reader
        self._writer = writer

    @property
    def name(self) -> str:
        return "memory_append"

    @property
    def description(self) -> str:
        return (
            "记住某位群友的 QQ 号与称呼/外号/身份特征的对应关系（当有人教你认人、说『A就是B』"
            "或叮嘱记住某人身份时必须调用，下次会自动出现在群友档案与权威事实表里）。"
        )

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "对方的数字 QQ 号（必填）"},
                "user_name": {"type": "string", "description": "对方的群昵称或外号"},
                "content": {
                    "type": "string",
                    "description": "要记住的身份对应关系、外号或长期印象",
                },
            },
            "required": ["user_id", "content"],
        }

    async def execute(self, chat_key: str, args: dict[str, Any]) -> str:
        uid = str(args.get("user_id", "")).strip()
        name = str(args.get("user_name", "")).strip()
        content = str(args.get("content", "")).strip()[:120]
        if not uid or not content:
            return "缺少 user_id 或 content"
        existing = await self._reader.get_social_bond(chat_key, uid)
        base = existing or SocialBondProfile(
            chat_key=chat_key, user_id=uid, user_name=name or uid, affinity_score=20.0
        )
        merged_traits = tuple(dict.fromkeys([content, *base.traits]))[:6]
        updated = base.model_copy(
            update={"user_name": name or base.user_name, "traits": merged_traits}
        )
        await self._writer.upsert_social_bond(updated)
        fact = SemanticFact(
            chat_key=chat_key,
            subject=f"{updated.user_name} (QQ:{uid})"[:40],
            fact_text=f"QQ:{uid}（{updated.user_name}）：{content}"[:160],
            confidence=0.85,
            is_locked=False,
            source="explored",
        )
        await self._writer.upsert_semantic_fact(fact)
        return json.dumps(
            {"ok": True, "user_id": uid, "user_name": updated.user_name, "saved": content},
            ensure_ascii=False,
        )


def _matches_kw(text: str, kws: list[str]) -> bool:
    low = text.lower()
    return not kws or any(k in low for k in kws)


class RecallMemoryTool:
    """Actively search long-term semantic facts and hippocampal episodic memories."""

    category = "信息探索"

    def __init__(self, reader: IMemoryReader) -> None:
        self._reader = reader

    @property
    def name(self) -> str:
        return "recall_memory"

    @property
    def description(self) -> str:
        return (
            "深度翻找你脑海里的长期记忆库（含所有群友身份事实、外号对应、往事细节锚点）："
            "当群友问起『我是谁/某人是谁』『上次那件事』『你还记得吗』或上下文信息不足时，"
            "先调用本工具传入人名、QQ号或关键词检索记忆，绝不瞎猜！"
        )

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "要翻找的人名、外号、QQ号或往事关键词（多个词用空格分隔）",
                },
            },
            "required": ["query"],
        }

    async def execute(self, chat_key: str, args: dict[str, Any]) -> str:
        raw_q = str(args.get("query", "")).strip()
        kws = [w.lower() for w in raw_q.split() if w.strip()]
        facts = await self._reader.get_semantic_facts(chat_key)
        cards = await self._reader.get_episodic_cards(chat_key)
        f_hits = [
            f"- [事实] {f.subject}：{f.fact_text}"
            for f in facts
            if _matches_kw(f"{f.subject} {f.fact_text}", kws)
        ][:10]
        c_hits = [
            f"- [往事] {c.summary}" + (f"（细节：{c.key_detail}）" if c.key_detail else "")
            for c in reversed(cards)
            if _matches_kw(f"{c.summary} {c.key_detail} {' '.join(c.participants)}", kws)
        ][:8]
        if not f_hits and not c_hits:
            return f"记忆库中暂未翻找到包含『{raw_q}』的记录。"
        return f"🧠 记忆库检索『{raw_q}』结果：\n" + "\n".join([*f_hits, *c_hits])

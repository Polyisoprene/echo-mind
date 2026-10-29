"""NoneBot2 OneBot V11 Bridge implementing IMessageSender & IGroupRosterReader."""

from __future__ import annotations

import asyncio
import base64
import json
import time
from pathlib import Path
from typing import Any, Literal
from urllib.parse import unquote, urlparse

from echomind.adapters.onebot.send_guard import OutboundDeduplicator, sanitize_outbound_text
from echomind.adapters.storage.database import SqliteDatabase
from echomind.domain.models import MediaAttachment, SocialBondProfile
from echomind.domain.ports import IOneBotApiCaller

RoleLiteral = Literal["owner", "admin", "member"]
MAX_INLINE_STICKER_BYTES = 8 * 1024 * 1024


def _local_sticker_path(file_ref: str) -> Path | None:
    """Return a readable local path when the reference is a file:// URI."""
    if not file_ref.lower().startswith("file://"):
        return None
    path = Path(unquote(urlparse(file_ref).path))
    return path if path.is_file() else None


def _read_sticker_bytes(path: Path) -> bytes:
    return path.read_bytes()


async def inline_sticker_ref(file_ref: str) -> str:
    """Inline local sticker files as base64.

    NapCat 跑在 Docker 容器里，宿主机绝对路径（file:///home/...）在容器内根本不存在，
    直接发 file:// 会静默失败。base64 内联不依赖路径挂载，是唯一天然可用的形态。
    """
    path = _local_sticker_path(file_ref)
    if path is None or path.stat().st_size > MAX_INLINE_STICKER_BYTES:
        return file_ref
    raw = await asyncio.to_thread(_read_sticker_bytes, path)
    return "base64://" + base64.b64encode(raw).decode("ascii")


def _parse_chat_key(chat_key: str) -> tuple[str, int]:
    parts = chat_key.split(":", 1)
    if len(parts) != 2 or not parts[1].isdigit():
        raise ValueError(f"Invalid chat_key: {chat_key}")
    return parts[0], int(parts[1])


def _build_segments(
    clean_text: str, reply_mid: str | None, at_uid: str | None
) -> list[dict[str, Any]]:
    segs: list[dict[str, Any]] = []
    if reply_mid:
        segs.append({"type": "reply", "data": {"id": reply_mid}})
    if at_uid:
        segs.append({"type": "at", "data": {"qq": at_uid}})
    if clean_text:
        segs.append({"type": "text", "data": {"text": clean_text}})
    return segs


def _map_member_role(raw_role: str) -> RoleLiteral:
    if raw_role == "owner":
        return "owner"
    if raw_role == "admin":
        return "admin"
    return "member"


def _dict_to_bond(group_id: str, item: dict[str, Any]) -> SocialBondProfile:
    uid = str(item.get("user_id", ""))
    card = str(item.get("card", "")).strip()
    nick = str(item.get("nickname", uid)).strip()
    name = card if card else nick
    role = _map_member_role(str(item.get("role", "member")))
    return SocialBondProfile(
        chat_key=f"group:{group_id}",
        user_id=uid,
        user_name=name,
        group_role=role,
    )


class OneBotV11Bridge:
    """Adapter satisfying IMessageSender & IGroupRosterReader over NoneBot2 OneBot V11."""

    def __init__(self, caller: IOneBotApiCaller, db: SqliteDatabase) -> None:
        self._caller = caller
        self._db = db
        self._dedup = OutboundDeduplicator()

    async def _record_self_message(
        self,
        chat_key: str,
        mid: str,
        text: str,
        media: tuple[MediaAttachment, ...] = (),
    ) -> None:
        now_ms = int(time.time() * 1000)
        media_str = json.dumps([m.model_dump() for m in media], ensure_ascii=False)
        sql = (
            "INSERT INTO chat_messages "
            "(chat_key, mid, ts, sender_id, sender_name, is_self, is_read, text, media_json) "
            "VALUES (?, ?, ?, 'self', '我', 1, 1, ?, ?)"
        )
        async with self._db.connect() as conn:
            await conn.execute(sql, (chat_key, mid, now_ms, text, media_str))
            await conn.commit()

    async def _dispatch_segments(self, chat_key: str, segments: list[dict[str, Any]]) -> str:
        kind, target_id = _parse_chat_key(chat_key)
        action = "send_private_msg" if kind == "private" else "send_group_msg"
        id_field = "user_id" if kind == "private" else "group_id"
        resp = await self._caller.call_api(action, **{id_field: target_id, "message": segments})
        mid = resp.get("message_id", "") if isinstance(resp, dict) else ""
        return str(mid)

    async def _normalize_reply_and_at(
        self, chat_key: str, reply_to_mid: str | None, at_user_id: str | None
    ) -> tuple[str | None, str | None, bool]:
        clean_at = at_user_id.strip() if at_user_id else None
        if not reply_to_mid:
            return None, clean_at, False
        clean_mid = reply_to_mid.lstrip("#").strip()
        if not clean_mid:
            return None, clean_at, False
        async with self._db.connect() as conn:
            c_mid = await conn.execute(
                "SELECT sender_id FROM chat_messages WHERE chat_key = ? AND mid = ? LIMIT 1",
                (chat_key, clean_mid),
            )
            mid_row = await c_mid.fetchone()
            if mid_row:
                q_uid = str(mid_row[0])
                third_party = bool(clean_at and q_uid and clean_at != q_uid)
                return clean_mid, clean_at, third_party
            c_uid = await conn.execute(
                "SELECT 1 FROM social_bonds WHERE chat_key = ? AND user_id = ? LIMIT 1",
                (chat_key, clean_mid),
            )
            if await c_uid.fetchone():
                return None, clean_at if clean_at else clean_mid, False
        return clean_mid, clean_at, False

    async def send_text(
        self,
        chat_key: str,
        messages: tuple[str, ...],
        reply_to_mid: str | None = None,
        at_user_id: str | None = None,
    ) -> tuple[str, ...]:
        eff_reply, eff_at, keep_both = await self._normalize_reply_and_at(
            chat_key, reply_to_mid, at_user_id
        )
        sent_ids: list[str] = []
        for idx, raw_msg in enumerate(messages):
            plan = sanitize_outbound_text(
                raw_msg,
                reply_to_mid=eff_reply if idx == 0 else None,
                at_user_id=eff_at if idx == 0 else None,
                preserve_both=(keep_both and idx == 0),
            )
            if not plan.clean_text and not plan.effective_at_uid:
                continue
            if self._dedup.is_duplicate(chat_key, plan.clean_text):
                continue
            segs = _build_segments(plan.clean_text, plan.effective_reply_mid, plan.effective_at_uid)
            mid = await self._dispatch_segments(chat_key, segs)
            await self._record_self_message(chat_key, mid, plan.clean_text.strip())
            sent_ids.append(mid)
        return tuple(sent_ids)

    async def _lookup_sticker_row(self, sticker_id: str) -> tuple[str, str]:
        sql = "SELECT local_file, url, local_note, desc_text FROM stickers WHERE id = ?"
        async with self._db.connect() as conn:
            cursor = await conn.execute(sql, (sticker_id,))
            row = await cursor.fetchone()
            if not row:
                return "", sticker_id
            file_ref = str(row[0]) if row[0] else str(row[1])
            label = str(row[2]) if row[2] else (str(row[3]) if row[3] else sticker_id)
            return file_ref, label

    async def _bump_sticker_usage(self, sticker_id: str) -> None:
        now_ms = int(time.time() * 1000)
        sql = "UPDATE stickers SET use_count = use_count + 1, last_used_at = ? WHERE id = ?"
        async with self._db.connect() as conn:
            await conn.execute(sql, (now_ms, sticker_id))
            await conn.commit()

    async def send_sticker(
        self, chat_key: str, sticker_id: str, reply_to_mid: str | None = None
    ) -> str | None:
        file_ref, label = await self._lookup_sticker_row(sticker_id)
        if not file_ref:
            return None
        file_ref = await inline_sticker_ref(file_ref)
        segs: list[dict[str, Any]] = []
        if reply_to_mid:
            segs.append({"type": "reply", "data": {"id": reply_to_mid}})
        segs.append({"type": "image", "data": {"file": file_ref}})
        mid = await self._dispatch_segments(chat_key, segs)
        await self._bump_sticker_usage(sticker_id)
        att = MediaAttachment(
            kind="image",
            url=file_ref,
            description=label,
            message_id=mid,
        )
        await self._record_self_message(
            chat_key, mid, f"[表情包:{label} (stickerId={sticker_id})]", (att,)
        )
        return mid

    async def send_voice(self, chat_key: str, audio_b64: str, summary_text: str) -> str | None:
        if not audio_b64:
            return None
        ref = audio_b64 if audio_b64.startswith("base64://") else f"base64://{audio_b64}"
        segs = [{"type": "record", "data": {"file": ref}}]
        mid = await self._dispatch_segments(chat_key, segs)
        await self._record_self_message(chat_key, mid, f"[语音:{summary_text}]")
        return mid

    async def send_poke(self, chat_key: str, target_user_id: str) -> bool:
        kind, chat_id = _parse_chat_key(chat_key)
        uid = int(target_user_id)
        if kind == "private":
            await self._caller.call_api("friend_poke", user_id=uid)
        else:
            await self._caller.call_api("group_poke", group_id=chat_id, user_id=uid)
        await self._record_self_message(chat_key, "", f"[拍一拍:{target_user_id}]")
        return True

    async def get_group_members(self, group_id: str) -> tuple[SocialBondProfile, ...]:
        raw = await self._caller.call_api("get_group_member_list", group_id=int(group_id))
        items = raw if isinstance(raw, list) else []
        return tuple(_dict_to_bond(group_id, item) for item in items if isinstance(item, dict))

"""Perceptual enrichment pipeline implementing IPerceptEnricher (OCP & Chain of Responsibility)."""

from __future__ import annotations

import json
import re
from typing import Any

from echomind.adapters.storage.database import SqliteDatabase
from echomind.domain.models import MediaAttachment, Percept
from echomind.domain.ports import ICaptionGateway, IPerceptEnricher

ACOUSTIC_ECHO_RE = re.compile(
    r"有回音|产生回音|听到回音|没有回音|回音壁|回音消除|"
    r"(?:麦克风|音响|空间|房间|山谷|耳机|喇叭).{0,6}回音|说一句回音"
)


class QuoteStickerEnricher:
    """Enrich quoted message text with local sticker descriptions & #messageId."""

    def __init__(self, db: SqliteDatabase, bot_names: tuple[str, ...] = ("回音", "尾尾")) -> None:
        self._db = db
        self._bot_names = bot_names

    def set_bot_names(self, names: tuple[str, ...]) -> None:
        """Hot-update the wake names used for call-by-name detection."""
        cleaned = tuple(dict.fromkeys(n.strip() for n in names if n.strip()))
        if cleaned:
            self._bot_names = cleaned

    async def _lookup_stored_quote(self, chat_key: str, mid: str) -> tuple[str, bool]:
        sql = (
            "SELECT text, is_self, sender_name FROM chat_messages "
            "WHERE chat_key = ? AND mid = ? LIMIT 1"
        )
        async with self._db.connect() as conn:
            cursor = await conn.execute(sql, (chat_key, mid))
            row = await cursor.fetchone()
            if not row:
                return "", False
            txt, is_self, s_name = str(row[0]), bool(row[1]), str(row[2] or "").strip()
            prefix = f"[{s_name}] " if s_name and not is_self else ""
            return f"{prefix}{txt}", is_self

    def _check_called_by_name(self, text: str) -> bool:
        cleaned = ACOUSTIC_ECHO_RE.sub("", text).lower()
        return any(name.lower() in cleaned for name in self._bot_names if name)

    async def enrich(self, percept: Percept) -> Percept:
        called = percept.is_called_by_name or self._check_called_by_name(percept.text)
        if not percept.quoted_message_id:
            return percept.model_copy(update={"is_called_by_name": called})

        stored_text, is_self = await self._lookup_stored_quote(
            percept.chat_key, percept.quoted_message_id
        )
        q_mid = percept.quoted_message_id
        resolved_quote = stored_text if stored_text else percept.quoted_text
        if not resolved_quote.startswith(f"#{q_mid}"):
            resolved_quote = f"#{q_mid} {resolved_quote}".strip()

        return percept.model_copy(
            update={
                "is_called_by_name": called,
                "is_quoted_me": percept.is_quoted_me or is_self,
                "quoted_text": resolved_quote,
            }
        )


def _extract_card_summary(raw_json_str: str) -> str:
    try:
        data: dict[str, Any] = json.loads(raw_json_str)
    except Exception:
        return ""
    prompt = str(data.get("prompt", "")).strip()
    meta = data.get("meta", {})
    detail = meta.get("detail_1", meta.get("news", meta.get("music", {})))
    if not isinstance(detail, dict):
        return prompt
    title = str(detail.get("title", detail.get("desc", ""))).strip()
    url = str(detail.get("qqdocurl", detail.get("jumpUrl", ""))).strip()
    parts = [p for p in (prompt, title, url) if p]
    return "[卡片: " + " | ".join(parts) + "]" if parts else ""


class CardAndForwardEnricher:
    """Parse mini-app/Bilibili JSON cards embedded in Percept text."""

    async def enrich(self, percept: Percept) -> Percept:
        if not percept.text.startswith("{"):
            return percept
        card_str = _extract_card_summary(percept.text)
        if not card_str:
            return percept
        return percept.model_copy(update={"text": card_str})


def _inject_caption_tag(text: str, m: MediaAttachment) -> str:
    if not m.description or m.kind != "image":
        return text
    tag = f"[图片:{m.description[:90]}]"
    if "[图片]" in text:
        return text.replace("[图片]", tag, 1)
    if not text.strip() or text.strip() == "[表情]":
        return tag
    return text


class ImageCaptionCacheEnricher:
    """Attach cached/live vision descriptions to MediaAttachments and Percept.text."""

    def __init__(self, db: SqliteDatabase, vision_gw: ICaptionGateway | None = None) -> None:
        self._db = db
        self._vision = vision_gw

    async def _lookup_caption(self, md5_key: str) -> str:
        if not md5_key:
            return ""
        sql = "SELECT description FROM image_caption_cache WHERE md5 = ?"
        async with self._db.connect() as conn:
            cursor = await conn.execute(sql, (md5_key.upper(),))
            row = await cursor.fetchone()
            return str(row[0]) if row else ""

    async def _describe_and_cache(self, att: MediaAttachment) -> str:
        ref = att.url or att.local_path
        if self._vision is None or not ref:
            return ""
        caption = str(await self._vision.describe_image(ref)).strip()
        if caption:
            await self._vision.cache_media_description(att, caption)
        return caption

    async def _enrich_single_media(self, att: MediaAttachment) -> MediaAttachment:
        if att.description or att.kind != "image":
            return att
        caption = await self._lookup_caption(att.local_path)
        if not caption:
            caption = await self._describe_and_cache(att)
        if not caption:
            return att
        return att.model_copy(update={"description": caption})

    async def enrich(self, percept: Percept) -> Percept:
        if not percept.media:
            return percept
        updated = [await self._enrich_single_media(m) for m in percept.media]
        new_txt = percept.text
        for m in updated:
            new_txt = _inject_caption_tag(new_txt, m)
        return percept.model_copy(update={"media": tuple(updated), "text": new_txt})


async def _safe_enrich(enricher: IPerceptEnricher, percept: Percept) -> Percept:
    """Isolate a faulty enricher so the inbound percept survives with a degraded field."""
    try:
        return await enricher.enrich(percept)
    except Exception:  # noqa: BLE001 - enrichment must degrade, never drop the message
        return percept


class PerceptEnrichmentPipeline:
    """Composite pipeline executing registered IPerceptEnricher instances sequentially."""

    def __init__(self, enrichers: tuple[IPerceptEnricher, ...]) -> None:
        self._enrichers = enrichers

    async def process(self, percept: Percept) -> Percept:
        """Run every enricher in order; a single failure must never drop the message."""
        current = percept
        for enricher in self._enrichers:
            current = await _safe_enrich(enricher, current)
        return current

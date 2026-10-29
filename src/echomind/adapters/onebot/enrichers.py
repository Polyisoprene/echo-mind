"""Perceptual enrichment pipeline implementing IPerceptEnricher (OCP & Chain of Responsibility)."""

from __future__ import annotations

import json
from typing import Any

from echomind.adapters.storage.database import SqliteDatabase
from echomind.domain.models import MediaAttachment, Percept
from echomind.domain.ports import IPerceptEnricher


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
        lower = text.lower()
        return any(name.lower() in lower for name in self._bot_names if name)

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


class ImageCaptionCacheEnricher:
    """Attach cached MD5 vision descriptions to MediaAttachments (0-token instant recognition)."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    async def _lookup_caption(self, md5_key: str) -> str:
        if not md5_key:
            return ""
        sql = "SELECT description FROM image_caption_cache WHERE md5 = ?"
        async with self._db.connect() as conn:
            cursor = await conn.execute(sql, (md5_key.upper(),))
            row = await cursor.fetchone()
            return str(row[0]) if row else ""

    async def _enrich_single_media(self, att: MediaAttachment) -> MediaAttachment:
        if att.description or att.kind != "image":
            return att
        caption = await self._lookup_caption(att.local_path)
        if not caption:
            return att
        return att.model_copy(update={"description": caption})

    async def enrich(self, percept: Percept) -> Percept:
        if not percept.media:
            return percept
        updated = [await self._enrich_single_media(m) for m in percept.media]
        return percept.model_copy(update={"media": tuple(updated)})


class PerceptEnrichmentPipeline:
    """Composite pipeline executing registered IPerceptEnricher instances sequentially."""

    def __init__(self, enrichers: tuple[IPerceptEnricher, ...]) -> None:
        self._enrichers = enrichers

    async def process(self, percept: Percept) -> Percept:
        current = percept
        for enricher in self._enrichers:
            current = await enricher.enrich(current)
        return current

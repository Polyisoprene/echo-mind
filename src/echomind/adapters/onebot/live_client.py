"""Live OneBot v11 HTTP Caller & WebSocket Event Loop with Debounce Batch Coalescing."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import httpx
import websockets

from echomind.adapters.llm.anchor import PrefixAnchorEngine
from echomind.adapters.onebot.enrichers import PerceptEnrichmentPipeline
from echomind.adapters.onebot.event_parser import parse_onebot_event
from echomind.adapters.onebot.forward_expander import expand_incoming_forward
from echomind.adapters.storage.database import SqliteDatabase
from echomind.domain.models import Percept
from echomind.domain.ports import ICognitiveCoreFacade
from echomind.mind.circadian import next_biological_heartbeat_sec
from echomind.mind.plasticity import compute_turn_social_reward
from echomind.runtime.agent_runner import AgentSessionRunner
from echomind.runtime.prompt_composer import StickerCandidate
from echomind.runtime.scheduler import CognitiveHeartbeatScheduler

STALE_TRIGGER_MS = 45_000


class OneBotHttpApiCaller:
    """Production IOneBotApiCaller sending POST requests to NapCat OneBot HTTP API."""

    def __init__(self, http_url: str, access_token: str = "") -> None:
        self._base = http_url.rstrip("/")
        self._token = access_token

    async def call_api(self, api: str, **data: Any) -> Any:
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
            resp = await client.post(f"{self._base}/{api}", headers=headers, json=data)
            resp.raise_for_status()
            body: dict[str, Any] = resp.json()
            return body.get("data", body)


async def _poll_ptt_text(caller: OneBotHttpApiCaller, mid: int | str) -> str:
    for attempt in range(4):
        try:
            data = await caller.call_api("fetch_ptt_text", message_id=mid)
        except Exception:
            data = None
        txt = str(data.get("text") or "").strip() if isinstance(data, dict) else ""
        if txt:
            return txt
        if attempt < 3:
            await asyncio.sleep(1.2)
    return ""


async def transcribe_incoming_voice(
    caller: Any, percept: Percept, bot_name: str = "回音"
) -> Percept:
    """Auto-transcribe incoming [语音] messages via NapCat fetch_ptt_text (with retry)."""
    has_voice = percept.text == "[语音]" or any(m.kind == "voice" for m in percept.media)
    if not has_voice or not percept.message_id.strip():
        return percept
    mid_str = percept.message_id.strip()
    mid: int | str = int(mid_str) if mid_str.lstrip("-").isdigit() else mid_str
    txt = await _poll_ptt_text(caller, mid)
    if not txt:
        return percept
    called = percept.is_called_by_name or (bot_name in txt) or ("尾尾" in txt)
    return percept.model_copy(update={"text": f"[语音转文字] {txt}", "is_called_by_name": called})


def _media_json(percept: Percept) -> str:
    if not percept.media:
        return ""
    return json.dumps(
        [
            {
                "kind": m.kind,
                "url": m.url,
                "local_path": m.local_path,
                "message_id": percept.message_id,
            }
            for m in percept.media
        ],
        ensure_ascii=False,
    )


def _apply_prefix_anchor(
    chat_key: str, chron: list[Any], anchor: PrefixAnchorEngine | None
) -> list[Any]:
    if anchor is None or not chron:
        return chron
    by_id = {(int(r[5]) if len(r) > 5 else int(r[1]) + idx): r for idx, r in enumerate(chron)}
    r_ids = tuple(by_id.keys())
    u_ids = tuple(dict.fromkeys(str(r[2]) for r in chron))
    dec = anchor.resolve(chat_key, r_ids, u_ids)
    kept = [by_id[k] for k in (*dec.anchored_ids, *dec.extra_ids) if k in by_id]
    return kept if kept else chron


def _rows_to_context(
    percept: Percept,
    h_rows: list[Any],
    s_rows: list[Any],
    anchor: PrefixAnchorEngine | None = None,
) -> tuple[tuple[Percept, ...], tuple[StickerCandidate, ...]]:
    chron = _apply_prefix_anchor(percept.chat_key, list(reversed(h_rows)), anchor)
    hist = tuple(
        Percept(
            chat_key=percept.chat_key, scene=percept.scene, message_id=str(r[0]),
            timestamp_ms=int(r[1]), sender_id=str(r[2]), sender_name=str(r[3]), text=str(r[4]),
        )
        for r in chron
    )
    stickers = tuple(
        StickerCandidate(
            sticker_id=str(r[0]),
            description=str(r[1] or r[2]),
            use_count=int(r[3]),
            tags=tuple(t for t in str(r[4] or "").split(",") if t),
        )
        for r in s_rows
    )
    return hist, stickers


def _filter_fresh_batch(batch: list[Percept], now_ms: int | None = None) -> tuple[Percept, ...]:
    """Drop triggers older than 45s relative to the newest trigger (or now_ms)."""
    if not batch:
        return ()
    anchor = now_ms if now_ms is not None else batch[-1].timestamp_ms
    fresh = [p for p in batch if (anchor - p.timestamp_ms) <= STALE_TRIGGER_MS]
    return tuple(fresh[-5:])


class OneBotLiveRuntime:
    """WebSocket listener with qq-agent style debounce batching & stale-turn protection."""

    def __init__(
        self, *, ws_url: str, access_token: str, self_id: str,
        allowed_groups: tuple[str, ...], owner_qq: str, db: SqliteDatabase,
        pipeline: PerceptEnrichmentPipeline, cognitive: ICognitiveCoreFacade,
        runner: AgentSessionRunner, scheduler: CognitiveHeartbeatScheduler,
        debounce_s: float = 0.0, http_url: str = "", allowed_private: tuple[str, ...] = (),
    ) -> None:
        self._ws_url, self._token, self._self_id = ws_url, access_token, self_id
        self._http_url = http_url or ws_url.replace("ws://", "http://").replace(":3001", ":3000")
        self._groups, self._owner_qq, self._db = frozenset(allowed_groups), owner_qq, db
        self._priv_users = frozenset(allowed_private)
        self._pipeline, self._cognitive, self._runner = pipeline, cognitive, runner
        self._scheduler, self._debounce_s = scheduler, debounce_s
        self._locks: dict[str, asyncio.Lock] = {}
        self._pending_batches: dict[str, list[Percept]] = {}
        self._wake_scheduled: set[str] = set()
        self._anchor = PrefixAnchorEngine(max_extra_read=10, window_size=48)

    async def _save_incoming(self, percept: Percept) -> None:
        sql_ins = (
            "INSERT INTO chat_messages "
            "(chat_key, mid, ts, sender_id, sender_name, is_self, text, media_json) "
            "VALUES (?, ?, ?, ?, ?, 0, ?, ?)"
        )
        row_args = (
            percept.chat_key, percept.message_id, percept.timestamp_ms,
            percept.sender_id, percept.sender_name, percept.text, _media_json(percept),
        )
        async with self._db.connect() as conn:
            await conn.execute(sql_ins, row_args)
            await conn.commit()

    async def _load_context(
        self, percept: Percept, trigger_mids: frozenset[str] = frozenset()
    ) -> tuple[tuple[Percept, ...], tuple[StickerCandidate, ...]]:
        sql_hist = (
            "SELECT mid, ts, sender_id, sender_name, text, id FROM chat_messages "
            "WHERE chat_key = ? ORDER BY id DESC LIMIT 65"
        )
        sql_st = "SELECT id, local_note, desc_text, use_count, scene_tags FROM stickers"
        async with self._db.connect() as conn:
            c1 = await conn.execute(sql_hist, (percept.chat_key,))
            raw_rows = list(await c1.fetchall())
            h_rows = [r for r in raw_rows if str(r[0]) not in trigger_mids][:50]
            c2 = await conn.execute(sql_st)
            s_rows = list(await c2.fetchall())
        return _rows_to_context(percept, h_rows, s_rows, self._anchor)

    async def _run_single_batch(self, chat_key: str, raw_batch: list[Percept]) -> None:
        triggers = _filter_fresh_batch(raw_batch)
        if not triggers:
            return
        last = triggers[-1]
        mids = frozenset(p.message_id for p in triggers if p.message_id)
        hist, stickers = await self._load_context(last, mids)
        is_owner = any(self._owner_qq and p.sender_id == self._owner_qq for p in triggers)
        reward = compute_turn_social_reward(
            " ".join(p.text for p in triggers),
            is_poke=any(p.is_poke_me for p in triggers),
            is_owner=is_owner,
        )
        await self._runner.run_turn(
            chat_key, hist, triggers, stickers=stickers, social_reward=reward
        )

    async def _drain_chat_batches(self, chat_key: str) -> None:
        lock = self._locks.setdefault(chat_key, asyncio.Lock())
        async with lock:
            while self._pending_batches.get(chat_key):
                raw_batch = self._pending_batches[chat_key][:]
                self._pending_batches[chat_key].clear()
                await self._run_single_batch(chat_key, raw_batch)

    async def handle_raw_event(self, ev: dict[str, Any]) -> bool:
        """Process a single OneBot event; coalesce rapid messages & skip stale backlog."""
        parsed = parse_onebot_event(
            ev, self._self_id, self._groups, self._owner_qq, self._priv_users
        )
        if parsed is None:
            return False
        caller = OneBotHttpApiCaller(self._http_url, self._token)
        fwd_expanded = await expand_incoming_forward(caller, parsed)
        piped = await self._pipeline.process(fwd_expanded)
        enriched = await transcribe_incoming_voice(caller, piped)
        await self._save_incoming(enriched)
        decision = await self._cognitive.evaluate_incoming(enriched)
        print(
            f"[EchoMind] 📩 {enriched.chat_key} {enriched.sender_name}: "
            f"{enriched.text[:30]} -> wake={decision.should_wake} ({decision.reason})",
            flush=True,
        )
        if not decision.should_wake:
            return False
        self._pending_batches.setdefault(enriched.chat_key, []).append(enriched)
        if enriched.chat_key in self._wake_scheduled:
            return True
        self._wake_scheduled.add(enriched.chat_key)
        try:
            if self._debounce_s > 0:
                await asyncio.sleep(self._debounce_s)
            await self._drain_chat_batches(enriched.chat_key)
        finally:
            self._wake_scheduled.discard(enriched.chat_key)
        return True

    async def _consume_ws_stream(self, ws: Any, stop_event: asyncio.Event) -> None:
        async for raw in ws:
            if stop_event.is_set():
                return
            ev = json.loads(str(raw))
            if isinstance(ev, dict):
                asyncio.create_task(self.handle_raw_event(ev))

    async def _connect_once(self, headers: dict[str, str], stop_event: asyncio.Event) -> None:
        async with websockets.connect(self._ws_url, additional_headers=headers) as ws:
            print(f"[EchoMind] ✅ Connected to NapCat WS: {self._ws_url}", flush=True)
            await self._consume_ws_stream(ws, stop_event)

    async def _run_heartbeat_loop(self, stop_event: asyncio.Event) -> None:
        default_group = f"group:{next(iter(self._groups))}" if self._groups else "group:10002002"
        while not stop_event.is_set():
            await asyncio.sleep(next_biological_heartbeat_sec())
            if stop_event.is_set():
                return
            await self._safe_heartbeat_tick(default_group)

    async def _safe_heartbeat_tick(self, default_group: str) -> None:
        try:
            await self._scheduler.run_heartbeat_cycle(default_group, int(time.time() * 1000))
        except Exception:
            return

    async def _ws_loop_body(self, headers: dict[str, str], stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                await self._connect_once(headers, stop_event)
            except Exception:
                await asyncio.sleep(3.0)

    async def run_ws_forever(self, stop_event: asyncio.Event) -> None:
        """Maintain persistent WebSocket connection & 5-min heartbeat/qzone loop."""
        headers = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        hb_task = asyncio.create_task(self._run_heartbeat_loop(stop_event))
        try:
            await self._ws_loop_body(headers, stop_event)
        finally:
            hb_task.cancel()

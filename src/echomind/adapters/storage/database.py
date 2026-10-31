"""SQLite WAL asynchronous connection manager and complete 14-table schema initializer."""

from __future__ import annotations

from pathlib import Path
from types import TracebackType

import aiosqlite

from echomind.adapters.storage.memory_migrations import ensure_columns
from echomind.adapters.storage.migrations import ensure_migrations

SCHEMA_DDL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_key TEXT NOT NULL,
    mid TEXT NOT NULL DEFAULT '',
    ts INTEGER NOT NULL,
    sender_id TEXT NOT NULL,
    sender_name TEXT NOT NULL,
    is_self INTEGER NOT NULL DEFAULT 0,
    is_read INTEGER NOT NULL DEFAULT 1,
    text TEXT NOT NULL,
    media_json TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_messages_chat_ts ON chat_messages(chat_key, ts);
CREATE INDEX IF NOT EXISTS idx_messages_chat_mid ON chat_messages(chat_key, mid);

CREATE TABLE IF NOT EXISTS working_state (
    scope_key TEXT PRIMARY KEY,
    valence REAL NOT NULL DEFAULT 20.0,
    energy REAL NOT NULL DEFAULT 85.0,
    jealousy REAL NOT NULL DEFAULT 0.0,
    shyness REAL NOT NULL DEFAULT 10.0,
    irritation REAL NOT NULL DEFAULT 0.0,
    inferiority REAL NOT NULL DEFAULT 10.0,
    express_index REAL NOT NULL DEFAULT 64.0,
    burst_until_ms INTEGER NOT NULL DEFAULT 0,
    curiosity_drive REAL NOT NULL DEFAULT 40.0,
    attachment_drive REAL NOT NULL DEFAULT 75.0,
    jealousy_drive REAL NOT NULL DEFAULT 0.0,
    social_drive REAL NOT NULL DEFAULT 35.0,
    current_activity TEXT NOT NULL DEFAULT '',
    inner_thought TEXT NOT NULL DEFAULT '',
    story_arc_json TEXT NOT NULL DEFAULT '{}',
    intentions_json TEXT NOT NULL DEFAULT '[]',
    curiosity_queue_json TEXT NOT NULL DEFAULT '[]',
    updated_at INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS episodic_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_key TEXT NOT NULL,
    ts INTEGER NOT NULL,
    msg_seq INTEGER NOT NULL DEFAULT 0,
    summary TEXT NOT NULL,
    key_detail TEXT NOT NULL DEFAULT '',
    participants_json TEXT NOT NULL DEFAULT '[]',
    importance REAL NOT NULL DEFAULT 3.0,
    pinned INTEGER NOT NULL DEFAULT 0,
    rehearsals INTEGER NOT NULL DEFAULT 0,
    last_recalled_ms INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_episodic_chat ON episodic_memories(chat_key, ts);

CREATE TABLE IF NOT EXISTS semantic_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_key TEXT NOT NULL,
    subject TEXT NOT NULL,
    fact_text TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.8,
    is_locked INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'peer',
    revision_count INTEGER NOT NULL DEFAULT 1,
    updated_at INTEGER NOT NULL DEFAULT 0,
    UNIQUE(chat_key, subject)
);

CREATE TABLE IF NOT EXISTS procedural_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_key TEXT NOT NULL,
    trigger_keyword TEXT NOT NULL,
    trigger_user_id TEXT NOT NULL DEFAULT '',
    action_instruction TEXT NOT NULL,
    strength INTEGER NOT NULL DEFAULT 3,
    UNIQUE(chat_key, trigger_keyword, trigger_user_id)
);

CREATE TABLE IF NOT EXISTS social_bonds (
    chat_key TEXT NOT NULL,
    user_id TEXT NOT NULL,
    user_name TEXT NOT NULL,
    group_role TEXT NOT NULL DEFAULT 'member',
    affinity_score REAL NOT NULL DEFAULT 0.0,
    affinity_level INTEGER NOT NULL DEFAULT 1,
    day_key TEXT NOT NULL DEFAULT '',
    day_gain REAL NOT NULL DEFAULT 0.0,
    msg_count INTEGER NOT NULL DEFAULT 0,
    last_seen_ms INTEGER NOT NULL DEFAULT 0,
    trust_score REAL NOT NULL DEFAULT 0.8,
    is_rival INTEGER NOT NULL DEFAULT 0,
    rival_reason TEXT NOT NULL DEFAULT '',
    traits_json TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY(chat_key, user_id)
);

CREATE TABLE IF NOT EXISTS persona_traits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL DEFAULT 'habit',
    trait_text TEXT NOT NULL UNIQUE,
    strength INTEGER NOT NULL DEFAULT 5,
    created_at INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS group_jargon (
    chat_key TEXT NOT NULL,
    term TEXT NOT NULL,
    meaning_or_sample TEXT NOT NULL DEFAULT '',
    hit_count INTEGER NOT NULL DEFAULT 1,
    user_count INTEGER NOT NULL DEFAULT 1,
    updated_at INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(chat_key, term)
);

CREATE TABLE IF NOT EXISTS topic_interests (
    topic TEXT PRIMARY KEY,
    weight REAL NOT NULL DEFAULT 1.0,
    updated_at INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS banned_phrases (
    phrase TEXT PRIMARY KEY,
    reason TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS plastic_params (
    key TEXT PRIMARY KEY,
    value REAL NOT NULL,
    min_bound REAL NOT NULL,
    max_bound REAL NOT NULL,
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS plastic_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    param_key TEXT NOT NULL,
    old_val REAL NOT NULL,
    new_val REAL NOT NULL,
    reward REAL NOT NULL DEFAULT 0.0,
    reason TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stickers (
    id TEXT PRIMARY KEY,
    emoji_id TEXT NOT NULL DEFAULT '',
    md5 TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL DEFAULT '',
    local_file TEXT NOT NULL DEFAULT '',
    desc_text TEXT NOT NULL DEFAULT '',
    local_note TEXT NOT NULL DEFAULT '',
    use_count INTEGER NOT NULL DEFAULT 0,
    last_used_at INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS image_caption_cache (
    md5 TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    hit_count INTEGER NOT NULL DEFAULT 1,
    updated_at INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_key TEXT NOT NULL,
    target_user_id TEXT NOT NULL DEFAULT '',
    remind_at_ms INTEGER NOT NULL,
    content TEXT NOT NULL,
    fired INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS exploration_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    kind TEXT NOT NULL,
    topic TEXT NOT NULL,
    tool_used TEXT NOT NULL DEFAULT '',
    finding_summary TEXT NOT NULL,
    spoke_chat_key TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS skill_configs (
    skill TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL DEFAULT '',
    updated_at INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (skill, key)
);

CREATE TABLE IF NOT EXISTS turn_traces (
    turn_id TEXT PRIMARY KEY,
    chat_key TEXT NOT NULL,
    ts INTEGER NOT NULL,
    trigger TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'done',
    rounds INTEGER NOT NULL DEFAULT 0,
    sent_count INTEGER NOT NULL DEFAULT 0,
    total_ms INTEGER NOT NULL DEFAULT 0,
    model TEXT NOT NULL DEFAULT '',
    context_count INTEGER NOT NULL DEFAULT 0,
    trigger_count INTEGER NOT NULL DEFAULT 0,
    system_prompt TEXT NOT NULL DEFAULT '',
    user_prompt TEXT NOT NULL DEFAULT '',
    steps_json TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_turn_chat_ts ON turn_traces(chat_key, ts DESC);

CREATE TABLE IF NOT EXISTS llm_traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    gateway_name TEXT NOT NULL,
    model_name TEXT NOT NULL,
    elapsed_ms INTEGER NOT NULL,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    cached_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    is_failover INTEGER NOT NULL DEFAULT 0,
    chat_key TEXT NOT NULL DEFAULT ''
);
"""


class _PragmaConnection:
    """Async context manager applying per-connection SQLite pragmas."""

    def __init__(self, db_path: Path) -> None:
        self._ctx = aiosqlite.connect(db_path)

    async def __aenter__(self) -> aiosqlite.Connection:
        conn = await self._ctx.__aenter__()
        await conn.execute("PRAGMA busy_timeout = 5000;")
        await conn.execute("PRAGMA synchronous = NORMAL;")
        await conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self._ctx.__aexit__(exc_type, exc_val, exc_tb)


class SqliteDatabase:
    """Async SQLite WAL connection provider with idempotent schema initialization."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    @property
    def path(self) -> Path:
        return self._db_path

    async def initialize(self) -> str:
        """Create parent directories, apply WAL mode & DDL, and return journal_mode."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.executescript(SCHEMA_DDL)
            await ensure_columns(conn)
            await ensure_migrations(conn)
            await conn.commit()
            cursor = await conn.execute("PRAGMA journal_mode;")
            row = await cursor.fetchone()
            return str(row[0]).lower() if row else "unknown"

    def connect(self) -> _PragmaConnection:
        """Return an async context-managed SQLite connection with per-connection pragmas."""
        return _PragmaConnection(self._db_path)

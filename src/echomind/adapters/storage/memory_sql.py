"""SQL fragments for semantic fact writes."""

UPSERT_FACT_SQL = (
    "INSERT INTO semantic_facts (chat_key, subject, fact_text, confidence, is_locked, "
    "source, revision_count, updated_at, scope, source_person_id, source_venue_id, "
    "owner_id, sensitivity, audience_json, source_quote, source_turn_id, event_time_ms, "
    "valid_to_ms) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
    "ON CONFLICT(chat_key, subject) DO UPDATE SET "
    "fact_text=excluded.fact_text, confidence=excluded.confidence, "
    "is_locked=excluded.is_locked, source=excluded.source, "
    "revision_count=excluded.revision_count, updated_at=excluded.updated_at, "
    "scope=excluded.scope, source_person_id=excluded.source_person_id, "
    "source_venue_id=excluded.source_venue_id, owner_id=excluded.owner_id, "
    "sensitivity=excluded.sensitivity, audience_json=excluded.audience_json, "
    "source_quote=excluded.source_quote, source_turn_id=excluded.source_turn_id, "
    "event_time_ms=excluded.event_time_ms, valid_to_ms=excluded.valid_to_ms"
)

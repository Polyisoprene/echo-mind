"""CLI: backfill social bonds from chat history (historical speakers)."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from echomind.adapters.storage.contact_backfill import backfill_contacts
from echomind.adapters.storage.database import SqliteDatabase


async def main() -> None:
    data_dir = Path(os.getenv("ECHOMIND_DATA_DIR", "data"))
    db = SqliteDatabase(data_dir / "echomind.db")
    report = await backfill_contacts(db, os.getenv("ECHOMIND_CHAT_KEY", ""))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python
"""Classify venue facts whose subject is a known person into scope=person.

Conservative: an embedded QQ that matches a known member, or a subject that is a
unique member name. Schema-like subjects (``自组织图式:``) are never reclassified.
Dry-run by default.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from collections import Counter
from pathlib import Path

QQ = re.compile(r"\d{5,12}")
SCHEMA_PREFIX = "自组织图式:"
DEFAULT_DB = Path("data/echomind.db")


def classify(db: Path) -> tuple[list[tuple[int, str, str, str]], Counter]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    users = {str(uid): str(name) for uid, name in conn.execute(
        "SELECT user_id, user_name FROM social_bonds"
    )}
    by_name: dict[str, set[str]] = {}
    for uid, name in users.items():
        by_name.setdefault(name, set()).add(uid)
    rows = list(conn.execute(
        "SELECT id, subject, chat_key FROM semantic_facts WHERE scope='venue'"
    ))
    plans: list[tuple[int, str, str, str]] = []
    reasons: Counter = Counter()
    for fact_id, subject, _chat in rows:
        text = str(subject).strip()
        if text.startswith(SCHEMA_PREFIX) or not text:
            reasons["schema_or_empty"] += 1
            continue
        match = QQ.search(text)
        if match and match.group(0) in users:
            plans.append((int(fact_id), match.group(0), text, "qq"))
            continue
        if text in by_name and len(by_name[text]) == 1:
            owner = next(iter(by_name[text]))
            plans.append((int(fact_id), owner, text, "unique_name"))
            continue
        reasons["unmatched"] += 1
    return plans, reasons


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    plans, reasons = classify(args.db)
    print(f"plans={len(plans)} reasons={dict(reasons)}")
    for fact_id, owner, subject, why in plans[:10]:
        print(f"  {fact_id} {subject!r} -> person {owner} ({why})")
    if args.apply and plans:
        conn = sqlite3.connect(args.db)
        conn.executemany(
            "UPDATE semantic_facts SET scope='person', owner_id=? WHERE id=?",
            [(owner, fact_id) for fact_id, owner, _s, _w in plans],
        )
        conn.commit()
        print(f"applied: {len(plans)} facts -> scope=person")
    elif plans:
        print("dry-run: pass --apply to write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

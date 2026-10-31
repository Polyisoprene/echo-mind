#!/usr/bin/env python
"""Reset the 7 persona baselines to their designed defaults (E1 follow-up, option A).

The pre-E2 plasticity moved the baseline on every turn; the values in the live DB are
the residue of that bug (e.g. possessiveness 93.4 against a default of 75). E2 stopped
further drift but does not undo it. This script does: it restores the defaults and
clears the fast state, pending observations and settlement timestamps.

Dry-run by default. Back up the database before `--apply`.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from echomind.domain.persona_specs import PERSONA_SPECS  # noqa: E402

DEFAULT_DB = ROOT / "data" / "echomind.db"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    keys = tuple(PERSONA_SPECS)
    before = {
        key: value
        for key, value in conn.execute("SELECT key, value FROM plastic_params")
        if key in keys
    }
    for key, spec in PERSONA_SPECS.items():
        conn.execute("UPDATE plastic_params SET value=? WHERE key=?", (spec.default, key))
    conn.execute("DELETE FROM persona_state")
    conn.execute("DELETE FROM persona_pending")
    conn.execute("DELETE FROM persona_settlement")

    for key in keys:
        old = before.get(key)
        print(f"{key:26s} {old if old is None else round(old, 2):>7} -> {spec_default(key):>7}")

    if args.apply:
        conn.commit()
        print("applied: baseline reset, state/pending/settlement cleared")
    else:
        conn.rollback()
        print("dry-run: pass --apply to write")
    conn.close()
    return 0


def spec_default(key: str) -> float:
    return PERSONA_SPECS[key].default


if __name__ == "__main__":
    raise SystemExit(main())

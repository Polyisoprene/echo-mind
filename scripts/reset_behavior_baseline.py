#!/usr/bin/env python
"""Reset the five behaviour parameters to their designed defaults.

Same origin as the persona reset: the pre-E2 plasticity moved these every turn, so
talkativeness (71 vs 58) and curiosity (79.5 vs 65) are residue, not learning.
Persona dimensions are handled by scripts/reset_persona_baseline.py.

Dry-run by default. Back up the database before `--apply`.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from echomind.adapters.storage.working_repo import DEFAULT_PLASTIC_PARAMS  # noqa: E402
from echomind.domain.persona_specs import PERSONA_SPECS  # noqa: E402

DEFAULT_DB = ROOT / "data" / "echomind.db"
BEHAVIOUR = tuple(spec for spec in DEFAULT_PLASTIC_PARAMS if spec.key not in PERSONA_SPECS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    keys = tuple(spec.key for spec in BEHAVIOUR)
    before = {
        key: value
        for key, value in conn.execute("SELECT key, value FROM plastic_params")
        if key in keys
    }
    for spec in BEHAVIOUR:
        conn.execute(
            "UPDATE plastic_params SET value=? WHERE key=?", (spec.value, spec.key)
        )
        old = before.get(spec.key)
        print(f"{spec.key:22s} {old if old is None else round(old, 2):>7} -> {spec.value:>7}")

    if args.apply:
        conn.commit()
        print("applied: behaviour parameters reset")
    else:
        conn.rollback()
        print("dry-run: pass --apply to write")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

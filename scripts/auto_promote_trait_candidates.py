#!/usr/bin/env python
"""CLI wrapper around the G1 auto-promotion service."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from echomind.adapters.storage.trait_auto_promotion import auto_promote

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "echomind.db")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    results = asyncio.run(auto_promote(args.db, args.apply))
    args.out = args.out or ROOT / "eval" / "baselines" / "auto-promotion-2026-11-01.json"
    args.out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

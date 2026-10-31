"""Maintain the parameter provenance ledger.

Usage:
    python scripts/param_audit.py --write    # merge scanned constants into the ledger
    python scripts/param_audit.py --report   # summarise coverage (default)

The ledger is the single place where a tunable constant earns the right to exist.
An entry that is `class: unknown` is visible debt: it is counted, ratcheted by
`param_gate.py`, and must be paid down before any claim about it can be made.
"""

from __future__ import annotations

import argparse
import collections
from typing import Any

import evidence_lib


def _summary(entries: list[dict[str, Any]]) -> str:
    by_class = collections.Counter(str(e["class"]) for e in entries)
    compliant = sum(1 for e in entries if evidence_lib.is_compliant(e))
    lines = [
        f"total constants : {len(entries)}",
        f"compliant       : {compliant}",
        f"debt            : {len(entries) - compliant}",
        "by class        : " + ", ".join(f"{k}={v}" for k, v in sorted(by_class.items())),
    ]
    per_module = collections.Counter(
        str(e["module"]) for e in entries if not evidence_lib.is_compliant(e)
    )
    if per_module:
        lines.append("worst modules   :")
        for module, count in per_module.most_common(8):
            lines.append(f"  {module}: {count}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="merge scan into ledger.json")
    parser.add_argument("--report", action="store_true", help="print coverage summary")
    args = parser.parse_args()

    scanned = evidence_lib.scan()
    if args.write:
        existing = evidence_lib.load_ledger()
        merged = evidence_lib.merge(existing, scanned)
        payload = {
            "version": 1,
            "generated_by": "scripts/param_audit.py",
            "entries": [merged[key] for key in sorted(merged)],
        }
        evidence_lib.save_json(evidence_lib.LEDGER_PATH, payload)
        target = evidence_lib.LEDGER_PATH.relative_to(evidence_lib.ROOT)
        print(f"wrote {len(merged)} entries -> {target}")

    has_ledger = evidence_lib.LEDGER_PATH.is_file()
    entries = list(evidence_lib.load_ledger().values()) if has_ledger else scanned
    print(_summary(entries))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Gate: every tunable constant must be declared in the provenance ledger.

Fails when:
  * a constant exists in code but not in the ledger (new undeclared tunable),
  * the ledger references a constant that no longer exists (stale entry),
  * an entry uses an unknown class or misses its class-specific evidence,
  * provenance debt grew beyond the recorded baseline (ratchet).

`--init-baseline` records the current state; it is an explicit act, never automatic.
"""

from __future__ import annotations

import argparse
import datetime
import sys
from typing import Any

import evidence_lib


def _missing(scanned: list[dict[str, Any]], ledger: dict[str, dict[str, Any]]) -> list[str]:
    return [str(e["id"]) for e in scanned if str(e["id"]) not in ledger]


def _stale(scanned: list[dict[str, Any]], ledger: dict[str, dict[str, Any]]) -> list[str]:
    live = {str(e["id"]) for e in scanned}
    return [key for key in ledger if key not in live]


def _invalid(ledger: dict[str, dict[str, Any]]) -> list[str]:
    problems: list[str] = []
    for key, entry in ledger.items():
        klass = str(entry.get("class", "unknown"))
        if klass not in evidence_lib.ALLOWED_CLASSES:
            problems.append(f"{key}: illegal class {klass!r}")
            continue
        if klass == "unknown":
            continue
        for field in evidence_lib.required_for(klass):
            if evidence_lib.get_field(entry, field) in (None, "", []):
                problems.append(f"{key}: class {klass} requires {field}")
    return problems


def _debt(ledger: dict[str, dict[str, Any]]) -> int:
    return sum(1 for entry in ledger.values() if not evidence_lib.is_compliant(entry))


def _collect(scanned: list[dict[str, Any]], ledger: dict[str, dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    missing = _missing(scanned, ledger)
    if missing:
        failures.append(f"{len(missing)} constants lack a ledger entry, e.g. {missing[:5]}")
    stale = _stale(scanned, ledger)
    if stale:
        failures.append(f"{len(stale)} stale ledger entries, e.g. {stale[:5]}")
    invalid = _invalid(ledger)
    if invalid:
        failures.append(f"{len(invalid)} entries miss required evidence, e.g. {invalid[:5]}")
    return failures


def _record_baseline(ledger: dict[str, dict[str, Any]], debt: int) -> None:
    payload = {
        "total": len(ledger),
        "debt": debt,
        "compliant": len(ledger) - debt,
        "recorded_at": datetime.date.today().isoformat(),
        "note": "debt may only shrink; raise deliberately with --init-baseline",
    }
    evidence_lib.save_json(evidence_lib.BASELINE_PATH, payload)
    print(f"baseline recorded: total={payload['total']} debt={debt}")


def _baseline_check(debt: int) -> tuple[list[str], int]:
    baseline = evidence_lib.load_json(evidence_lib.BASELINE_PATH)
    if not baseline:
        return ["baseline missing; run `python scripts/param_gate.py --init-baseline` once"], 0
    recorded = int(baseline.get("debt", 0))
    if debt <= recorded:
        return [], recorded
    message = f"provenance debt grew: {recorded} -> {debt} (annotate or remove the constant)"
    return [message], recorded


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--init-baseline", action="store_true", help="record current debt as baseline"
    )
    args = parser.parse_args()

    if not evidence_lib.LEDGER_PATH.is_file():
        print("FAIL: ledger missing; run `python scripts/param_audit.py --write` first")
        return 1

    scanned = evidence_lib.scan()
    ledger = evidence_lib.load_ledger()
    debt = _debt(ledger)

    if args.init_baseline:
        _record_baseline(ledger, debt)
        return 0

    failures = _collect(scanned, ledger)
    baseline_failures, recorded = _baseline_check(debt)
    failures.extend(baseline_failures)

    compliant = len(ledger) - debt
    print(f"constants={len(ledger)} compliant={compliant} debt={debt} baseline={recorded}")
    if failures:
        for line in failures:
            print(f"FAIL: {line}")
        return 1
    print("OK: parameter ledger consistent")
    return 0


if __name__ == "__main__":
    sys.exit(main())

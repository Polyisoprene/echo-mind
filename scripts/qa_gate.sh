#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
cd "$(dirname "$0")/.."

echo "================================================================"
echo "🛡️  [Gate 1A] Ruff Static Lint (PEP8 + SIM + RET + C4 + C901<=6)"
echo "================================================================"
uv run ruff check src tests

echo "================================================================"
echo "🛡️  [Gate 1B] Radon Cyclomatic Complexity (Grade A Required)"
echo "================================================================"
uv run radon cc src -a -nb
BAD_CC=$(uv run radon cc src -nc | wc -l)
if [ "$BAD_CC" -gt 0 ]; then
  echo "❌ Radon found functions with complexity grade worse than B!"
  uv run radon cc src -nc
  exit 1
fi

echo "================================================================"
echo "🛡️  [Gate 1C] Pylint Anti-Nesting Check (max-nested-blocks <= 2)"
echo "================================================================"
uv run pylint src/echomind

echo "================================================================"
echo "🛡️  [Gate 2] Mypy 100% Strict Static Type & LSP Verification"
echo "================================================================"
uv run mypy --strict src tests

echo "================================================================"
echo "🛡️  [Gate 2B] Parameter Provenance Ledger (docs/params/ledger.json)"
echo "================================================================"
uv run python scripts/param_gate.py

echo "================================================================"
echo "🛡️  [Gate 2C] Capability Ledger (docs/capabilities.json)"
echo "================================================================"
uv run python scripts/capability_gate.py --check

echo "================================================================"
echo "🛡️  [Gate 3 & 4] AST Flat-Code/SOLID Boundaries & Pytest (>=90%)"
echo "================================================================"
uv run pytest --cov=src/echomind --cov-report=term-missing --cov-fail-under=90
uv run coverage report --fail-under=90

echo "================================================================"
echo "✅ ALL INDUSTRIAL QA & ANTI-NESTING GATES PASSED (via uv run)!"
echo "================================================================"

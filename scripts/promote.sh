#!/usr/bin/env bash
# Stage 29 交付闸门：只允许「在 A 线跑过全门禁 + 回放」的提交进入 main。
set -euo pipefail
A_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
B_DIR="${ECHOMIND_B_DIR:-$A_DIR/../echo-mind}"
SHA="$(git -C "$A_DIR" rev-parse --short HEAD)"

if [[ -n "$(git -C "$A_DIR" status --porcelain)" ]]; then
  echo "[promote] A 线工作区不干净，先提交或还原" >&2; exit 2
fi

echo "[promote] 1/3 在 A 线跑 7 道门禁…"
(cd "$A_DIR" && ./scripts/qa_gate.sh) | tail -3

echo "[promote] 2/3 在 A 线跑 120 回合回放…"
SNAP="$A_DIR/data/replay-snapshot.db"
if [[ -f "$SNAP" ]]; then
  (cd "$A_DIR" && uv run python scripts/replay_eval.py --db "$SNAP" \
      --chat-key "${ECHOMIND_REPLAY_CHAT:-group:10002002}" --owner "${ECHOMIND_REPLAY_OWNER:-}" \
      --turns 120 --out reports/) | grep -E '"(turns|wakes|probe_calls|double_apply|reward_spread)"'
else
  echo "[promote] 未找到回放快照，跳过回放（仅门禁）" >&2
fi

echo "[promote] 3/3 记录证据并合入 main…"
mkdir -p "$A_DIR/reports"
{ echo "commit=$SHA"; echo "date=$(date -Is)"; echo "gate=pass"; } > "$A_DIR/reports/promotion_${SHA}.txt"
COMMITS="$(git -C "$A_DIR" log --reverse --format='%H %s' "main..HEAD" | grep -v ' docs(' | cut -d' ' -f1 || true)"
if [[ -z "$COMMITS" ]]; then echo "[promote] 无待合入提交"; exit 0; fi
GIT_EDITOR=true git -C "$B_DIR" cherry-pick $COMMITS
echo "[promote] 完成：B 线 $(git -C "$B_DIR" rev-parse --short HEAD)"

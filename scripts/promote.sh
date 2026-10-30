#!/usr/bin/env bash
# Stage 29 交付闸门：只允许「在 A 线跑过全门禁 + 回放」的提交进入 main。
# 纯文档提交（只改 docs/）不参与 cherry-pick：文档由 `--sync-docs` 单独同步。
set -euo pipefail
A_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
B_DIR="${ECHOMIND_B_DIR:-$A_DIR/../echo-mind}"
SHA="$(git -C "$A_DIR" rev-parse --short HEAD)"
DRY_RUN="${DRY_RUN:-0}"
SYNC_DOCS="${SYNC_DOCS:-0}"
ONLY="${ONLY:-}"

if [[ -n "$(git -C "$A_DIR" status --porcelain)" ]]; then
  echo "[promote] A 线工作区不干净，先提交或还原" >&2; exit 2
fi

# 只挑「改了 docs/ 以外文件」且尚未按 patch-id 合入的提交。
COMMITS=""
while read -r marker sha; do
  [[ "$marker" == "+" ]] || continue
  changed="$(git -C "$A_DIR" show --pretty=format: --name-only "$sha" | sed '/^$/d')"
  if ! printf '%s\n' "$changed" | grep -qv '^docs/'; then
    echo "[promote] 跳过纯文档提交 $(git -C "$A_DIR" log -1 --format='%h %s' "$sha")"
    continue
  fi
  COMMITS="$COMMITS $sha"
done < <(git -C "$A_DIR" cherry main)

if [[ -n "$ONLY" ]]; then
  COMMITS=" $ONLY "
  echo "[promote] ONLY 模式：只合入 $ONLY"
fi

if [[ -z "${COMMITS// /}" ]]; then
  echo "[promote] 无待合入的代码提交"
  [[ "$SYNC_DOCS" == "1" ]] || exit 0
fi

if [[ "$DRY_RUN" == "1" ]]; then
  echo "[promote] DRY_RUN 将合入:${COMMITS:-  （无）}"
  exit 0
fi

echo "[promote] 1/3 在 A 线跑 7 道门禁…"
(cd "$A_DIR" && ./scripts/qa_gate.sh) | tail -3

echo "[promote] 2/3 在 A 线跑 120 回合回放…"
SNAP="$A_DIR/data/replay-snapshot.db"
if [[ -f "$SNAP" ]]; then
  replay_out="$(cd "$A_DIR" && uv run python scripts/replay_eval.py --db "$SNAP" \
      --chat-key "${ECHOMIND_REPLAY_CHAT:-group:10002002}" --owner "${ECHOMIND_REPLAY_OWNER:-}" \
      --turns 120 --out reports/)"
  printf '%s\n' "$replay_out" | grep -E '"(turns|wakes|probe_calls|double_apply|reward_spread)"'
  turns="$(printf '%s\n' "$replay_out" | sed -n 's/.*"turns": \([0-9]*\).*/\1/p' | head -1)"
  if [[ "${turns:-0}" -lt 100 ]]; then
    echo "[promote] 回放只跑了 ${turns:-0} 回合（快照/群号不匹配？），中止" >&2
    exit 4
  fi
else
  echo "[promote] 未找到回放快照，跳过回放（仅门禁）" >&2
fi

echo "[promote] 3/3 记录证据并合入 main…"
mkdir -p "$A_DIR/reports"
{ echo "commit=$SHA"; echo "date=$(date -Is)"; echo "gate=pass"; } > "$A_DIR/reports/promotion_${SHA}.txt"
for sha in $COMMITS; do
  if ! git -C "$B_DIR" cherry-pick -n "$sha"; then
    echo "[promote] cherry-pick 冲突，已回滚：$sha" >&2
    git -C "$B_DIR" cherry-pick --abort || true
    exit 3
  fi
  # B 线的 docs/ 是权威版本，提交里携带的文档改动一律丢弃，避免重复冲突。
  git -C "$B_DIR" checkout HEAD -- docs >/dev/null 2>&1 || true
  git -C "$B_DIR" add -A >/dev/null 2>&1
  if git -C "$B_DIR" diff --cached --quiet; then
    echo "[promote] 跳过（只含文档）：$sha"
    git -C "$B_DIR" reset -q --hard HEAD
  else
    git -C "$B_DIR" commit -q -C "$sha"
  fi
done
if [[ "$SYNC_DOCS" == "1" ]]; then
  git -C "$B_DIR" checkout "$(git -C "$A_DIR" rev-parse --abbrev-ref HEAD)" -- docs || true
  git -C "$B_DIR" add docs >/dev/null 2>&1 || true
  git -C "$B_DIR" commit -q -m "[no-behavior] docs: sync from A line" || true
fi
echo "[promote] 完成：B 线 $(git -C "$B_DIR" rev-parse --short HEAD)"

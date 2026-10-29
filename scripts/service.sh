#!/usr/bin/env bash
# EchoMind 生产服务启停脚本（单实例守护，避免 pkill 误杀 screen 内部 while 循环）
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCREEN_NAME="qqagent2"
PORT="${ECHOMIND_PORT:-3310}"
LOG_FILE="$APP_DIR/data/console.log"
UVICORN_TARGET="echomind.main:build_live_asgi_app"

export PATH="$HOME/.local/bin:$PATH"
cd "$APP_DIR"

is_running() {
  pgrep -f "/.venv/bin/uvicorn ${UVICORN_TARGET}" >/dev/null 2>&1
}

do_start() {
  if is_running; then
    echo "[service] 已在运行，跳过启动"
    return 0
  fi
  mkdir -p "$APP_DIR/data"
  : > "$LOG_FILE"
  screen -dmS "$SCREEN_NAME" bash -c \
    "export PATH=\"\$HOME/.local/bin:\$PATH\"; cd \"$APP_DIR\" && while true; do uv run uvicorn ${UVICORN_TARGET} --factory --host 0.0.0.0 --port ${PORT} >> \"$LOG_FILE\" 2>&1; sleep 3; done" \
    </dev/null >/dev/null 2>&1
  for _ in $(seq 1 20); do
    sleep 0.5
    if curl -sf --max-time 2 "http://127.0.0.1:${PORT}/api/mind/snapshot" >/dev/null 2>&1; then
      echo "[service] 启动成功：http://0.0.0.0:${PORT}"
      return 0
    fi
  done
  echo "[service] 启动超时，请查看 $LOG_FILE" >&2
  return 1
}

do_stop() {
  # 只杀真正的 venv uvicorn 进程，绝不 pkill 含目标字符串的 screen/bash 包装层
  pkill -f "/.venv/bin/uvicorn ${UVICORN_TARGET}" 2>/dev/null || true
  sleep 1
  if screen -ls 2>/dev/null | grep -q "\.${SCREEN_NAME}"; then
    screen -S "$SCREEN_NAME" -X quit 2>/dev/null || true
  fi
  echo "[service] 已停止"
}

do_status() {
  if is_running; then
    echo "[service] 运行中 (port ${PORT})"
    curl -s --max-time 3 "http://127.0.0.1:${PORT}/api/mind/snapshot" | head -c 400
    echo ""
  else
    echo "[service] 未运行"
    return 1
  fi
}

case "${1:-status}" in
  start)   do_start ;;
  stop)    do_stop ;;
  restart) do_stop; do_start ;;
  status)  do_status ;;
  log)     tail -n "${2:-40}" "$LOG_FILE" ;;
  *)       echo "用法: $0 {start|stop|restart|status|log [行数]}" >&2; exit 2 ;;
esac

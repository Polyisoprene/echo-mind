#!/usr/bin/env bash
# 本机建立到 192.168.3.114:3310 的 SSH 端口转发，绕过 Clash/FlClash 对局域网流量的代理拦截
set -euo pipefail

REMOTE_HOST="${ECHOMIND_REMOTE:-polyisoprene@192.168.3.114}"
LOCAL_PORT="${ECHOMIND_LOCAL_PORT:-3310}"
REMOTE_PORT="${ECHOMIND_REMOTE_PORT:-3310}"
SOCK="${ECHOMIND_SSH_SOCK:-/tmp/echomind-tunnel}"

is_up() {
  curl -s --noproxy '*' --max-time 2 -o /dev/null "http://127.0.0.1:${LOCAL_PORT}/" 2>/dev/null
}

case "${1:-start}" in
  start)
    if is_up; then
      echo "[tunnel] 已就绪：http://127.0.0.1:${LOCAL_PORT}/"
      exit 0
    fi
    if [[ ! -S "$SOCK" ]]; then
      ssh -fNM -S "$SOCK" -o ServerAliveInterval=30 "$REMOTE_HOST"
      sleep 1
    fi
    ssh -f -N -o ExitOnForwardFailure=yes \
        -L "${LOCAL_PORT}:127.0.0.1:${REMOTE_PORT}" -S "$SOCK" "$REMOTE_HOST"
    sleep 1
    if is_up; then
      echo "[tunnel] 已建立：http://127.0.0.1:${LOCAL_PORT}/  ->  ${REMOTE_HOST}:${REMOTE_PORT}"
    else
      echo "[tunnel] 建立失败" >&2
      exit 1
    fi
    ;;
  stop)
    ssh -S "$SOCK" -O cancel -L "${LOCAL_PORT}:127.0.0.1:${REMOTE_PORT}" "$REMOTE_HOST" 2>/dev/null || true
    echo "[tunnel] 已取消"
    ;;
  status)
    if is_up; then
      echo "[tunnel] 运行中：http://127.0.0.1:${LOCAL_PORT}/"
    else
      echo "[tunnel] 未运行"
      exit 1
    fi
    ;;
  *)
    echo "用法: $0 {start|stop|status}" >&2
    exit 2
    ;;
esac

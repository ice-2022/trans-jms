#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$BASE_DIR/logs"
PID_FILE="$LOG_DIR/service.pid"
LOG_FILE="$LOG_DIR/service.log"

mkdir -p "$LOG_DIR"

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" >/dev/null 2>&1; then
  echo "service already running, pid=$(cat "$PID_FILE")"
  exit 0
fi

nohup python3 "$BASE_DIR/service.py" >>"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"

echo "service started, pid=$(cat "$PID_FILE"), log=$LOG_FILE"

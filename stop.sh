#!/usr/bin/env sh
set -eu
if (set -o pipefail) >/dev/null 2>&1; then
  set -o pipefail
fi

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$BASE_DIR/logs"
PID_FILE="$LOG_DIR/service.pid"

if [ ! -f "$PID_FILE" ]; then
  echo "service not running (pid file not found)"
  exit 0
fi

PID="$(cat "$PID_FILE")"
if [ -z "$PID" ] || ! kill -0 "$PID" >/dev/null 2>&1; then
  echo "stale pid file found, removing: $PID_FILE"
  rm -f "$PID_FILE"
  exit 0
fi

kill "$PID"

i=1
while [ "$i" -le 20 ]; do
  if ! kill -0 "$PID" >/dev/null 2>&1; then
    rm -f "$PID_FILE"
    echo "service stopped, pid=$PID"
    exit 0
  fi
  sleep 1
  i=$((i + 1))
done

echo "service did not stop in time, force killing pid=$PID"
kill -9 "$PID"
rm -f "$PID_FILE"
echo "service force stopped, pid=$PID"

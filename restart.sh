#!/usr/bin/env sh
set -eu
if (set -o pipefail) >/dev/null 2>&1; then
  set -o pipefail
fi

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"

sh "$BASE_DIR/stop.sh"
sh "$BASE_DIR/start.sh"

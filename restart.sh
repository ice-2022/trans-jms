#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"

bash "$BASE_DIR/stop.sh"
bash "$BASE_DIR/start.sh"

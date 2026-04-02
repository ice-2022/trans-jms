#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
REQ_FILE="$BASE_DIR/requirements.txt"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found, please install Python 3 first"
  exit 1
fi

if [ ! -f "$REQ_FILE" ]; then
  echo "requirements.txt not found: $REQ_FILE"
  exit 1
fi

python3 -m pip install --upgrade pip
python3 -m pip install -r "$REQ_FILE"

echo "dependencies installed successfully"

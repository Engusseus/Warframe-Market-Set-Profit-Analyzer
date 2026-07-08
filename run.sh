#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"
CLI_BIN="$VENV_DIR/bin/wf-market-analyzer"

cd "$SCRIPT_DIR"

if [ -x "$CLI_BIN" ]; then
  exec "$CLI_BIN" "$@"
fi

if [ -x "$PYTHON_BIN" ]; then
  exec "$PYTHON_BIN" -m wf_market_analyzer "$@"
fi

echo "No installed analyzer was found in $VENV_DIR." >&2
echo "This launcher does not create environments or install packages during startup." >&2
echo "Create .venv and install the project explicitly first; see README.md." >&2
exit 1

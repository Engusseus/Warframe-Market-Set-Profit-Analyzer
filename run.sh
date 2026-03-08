#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"
CLI_BIN="$VENV_DIR/bin/wf-market-analyzer"

cd "$SCRIPT_DIR"

create_virtualenv() {
  if python3 -m venv "$VENV_DIR"; then
    return 0
  fi

  if python3 -m virtualenv "$VENV_DIR"; then
    return 0
  fi

  echo "Failed to create .venv." >&2
  echo "Install python3-venv or python3-virtualenv, then rerun ./run.sh." >&2
  return 1
}

repair_virtualenv() {
  echo "Repairing .venv because pip is missing..."

  if python3 -m virtualenv "$VENV_DIR"; then
    return 0
  fi

  echo "Failed to repair .venv." >&2
  echo "Delete .venv, install python3-venv or python3-virtualenv, and rerun ./run.sh." >&2
  return 1
}

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required to bootstrap this project." >&2
  echo "Install python3, then rerun ./run.sh." >&2
  exit 1
fi

if [ ! -x "$PYTHON_BIN" ]; then
  echo "Creating virtual environment in $VENV_DIR"
  create_virtualenv
fi

if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
  repair_virtualenv
fi

echo "Upgrading pip inside .venv..."
if ! "$PYTHON_BIN" -m pip install --upgrade pip; then
  echo "Failed to upgrade pip inside .venv." >&2
  exit 1
fi

echo "Installing the analyzer into .venv..."
if ! "$PYTHON_BIN" -m pip install --upgrade .; then
  echo "Failed to install the analyzer into .venv." >&2
  exit 1
fi

if [ -x "$CLI_BIN" ]; then
  exec "$CLI_BIN" "$@"
fi

exec "$PYTHON_BIN" -m wf_market_analyzer "$@"

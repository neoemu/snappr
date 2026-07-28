#!/usr/bin/env bash
# Run Shottr-Linux, creating/installing the virtualenv on first use.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$HERE/.venv"

if [ ! -d "$VENV" ]; then
    echo "Criando virtualenv em $VENV ..."
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install --upgrade pip
    "$VENV/bin/pip" install -r "$HERE/requirements.txt"
fi

exec "$VENV/bin/python" "$HERE/main.py" "$@"

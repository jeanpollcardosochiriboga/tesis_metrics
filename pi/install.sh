#!/usr/bin/env bash
# Installs collect_resources.py + Python venv on the Pi.
# Usage:  ./install.sh raspberry1@192.168.1.10
#
# Requires sshpass + PI_PASS env var (or interactive password).
set -euo pipefail

DEST="${1:-raspberry1@192.168.1.10}"
HERE="$(cd "$(dirname "$0")" && pwd)"
REMOTE_DIR="/home/raspberry1/tesis_metrics"

# Pull password from .env if present.
ENV_FILE="$HERE/../.env"
[ -f "$ENV_FILE" ] && set -a && . "$ENV_FILE" && set +a

if [ -z "${PI_PASS:-}" ]; then
    echo "PI_PASS not set; will prompt interactively." >&2
    SSH() { ssh -o StrictHostKeyChecking=accept-new "$@"; }
    SCP() { scp -o StrictHostKeyChecking=accept-new "$@"; }
else
    export SSHPASS="$PI_PASS"
    SSH() { sshpass -e ssh -o StrictHostKeyChecking=accept-new "$@"; }
    SCP() { sshpass -e scp -o StrictHostKeyChecking=accept-new "$@"; }
fi

echo "[install] Creating $REMOTE_DIR on Pi"
SSH "$DEST" "mkdir -p $REMOTE_DIR/bin $REMOTE_DIR/sessions"

echo "[install] Copying collect_resources.py"
SCP "$HERE/collect_resources.py" "$DEST:$REMOTE_DIR/bin/collect_resources.py"
SSH "$DEST" "chmod +x $REMOTE_DIR/bin/collect_resources.py"

echo "[install] Setting up Python venv on Pi (psutil + docker)"
SSH "$DEST" "python3 -m venv $REMOTE_DIR/venv && \
             $REMOTE_DIR/venv/bin/pip install --quiet --upgrade pip && \
             $REMOTE_DIR/venv/bin/pip install --quiet psutil docker"

echo "[install] Verifying"
SSH "$DEST" "$REMOTE_DIR/venv/bin/python -c 'import psutil, docker; print(\"psutil\", psutil.__version__, \"docker\", docker.__version__)'"

echo "[install] OK"

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$(dirname "$SCRIPT_DIR")"
DEST="$HOME/bin/feed_harvester"

echo "Deploying feed_harvester DEV → PROD..."

mkdir -p "$DEST/src"

cp "$SRC/src/"*.py "$DEST/src/"
cp "$SRC/requirements.txt" "$DEST/"

# Install/update systemd unit
UNIT_DIR="$HOME/.config/systemd/user"
mkdir -p "$UNIT_DIR"
cp "$SRC/systemd/feed-harvester.service" "$UNIT_DIR/"
systemctl --user daemon-reload

# Create/update venv
VENV="$DEST/.venv"
if [[ ! -d "$VENV" ]]; then
    python3 -m venv "$VENV"
    echo "Created venv at $VENV"
fi
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -r "$DEST/requirements.txt"

echo "Restarting feed-harvester service..."
systemctl --user restart feed-harvester

if systemctl --user is-active --quiet feed-harvester; then
    echo "Deployment successful."
else
    echo "Service failed to start. Check logs:"
    echo "  journalctl --user -u feed-harvester -n 20"
fi

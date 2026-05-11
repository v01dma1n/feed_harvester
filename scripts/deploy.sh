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

PYTHON="$HOME/.pyenv/versions/ml-env/bin/python"
PIP="$HOME/.pyenv/versions/ml-env/bin/pip"

"$PIP" install -q --upgrade pip
"$PIP" install -q -r "$DEST/requirements.txt"

echo "Restarting feed-harvester service..."
systemctl --user restart feed-harvester

if systemctl --user is-active --quiet feed-harvester; then
    echo "Deployment successful."
else
    echo "Service failed to start. Check logs:"
    echo "  journalctl --user -u feed-harvester -n 20"
fi

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$(dirname "$SCRIPT_DIR")"
REMOTE="tao14"
REMOTE_DEST="$REMOTE:~/bin/feed_harvester"
PIP="~/.pyenv/versions/ml-env/bin/pip"

echo "Deploying feed_harvester to $REMOTE..."

rsync -av "$SRC/src/" "$REMOTE_DEST/src/"
scp "$SRC/requirements.txt" "$REMOTE_DEST/requirements.txt"

# Install/update systemd unit
scp "$SRC/systemd/feed-harvester.service" "$REMOTE:~/.config/systemd/user/feed-harvester.service"
ssh "$REMOTE" "systemctl --user daemon-reload"

# Install dependencies
ssh "$REMOTE" "$PIP install -q --upgrade pip && $PIP install -q -r ~/bin/feed_harvester/requirements.txt"

echo "Restarting feed-harvester service on $REMOTE..."
ssh "$REMOTE" "systemctl --user restart feed-harvester"

if ssh "$REMOTE" "systemctl --user is-active --quiet feed-harvester"; then
    echo "Deployment successful."
else
    echo "Service failed to start. Check logs:"
    echo "  ssh $REMOTE 'journalctl --user -u feed-harvester -n 20'"
fi

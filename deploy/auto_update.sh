#!/usr/bin/env bash
# Server-side auto deploy: checks GitHub for new commits on main and deploys them.
# Run every few minutes by courier-autoupdate.timer (see deploy/README.md).
# If the app doesn't come back healthy after an update, it rolls back automatically.
set -euo pipefail

APP_DIR=/home/ubuntu/courier_app/courier_tracker
APP_USER=ubuntu
SERVICE=courier.service
HEALTH_URL=http://localhost:5000/login
BRANCH=main
BAD_FILE=/var/tmp/courier-autoupdate-bad-commit

exec 9>/tmp/courier-autoupdate.lock
flock -n 9 || { echo "Another update is running, skipping."; exit 0; }

cd "$APP_DIR"
as_app() { sudo -u "$APP_USER" -H "$@"; }

as_app git fetch -q origin "$BRANCH"
OLD=$(as_app git rev-parse HEAD)
NEW=$(as_app git rev-parse "origin/$BRANCH")
# The running code is OLD. Record it once so /healthz can report the deployed commit.
[ -s "$APP_DIR/.deployed_commit" ] || echo "$OLD" > "$APP_DIR/.deployed_commit"
[ "$OLD" = "$NEW" ] && exit 0
[ -f "$BAD_FILE" ] && [ "$(cat "$BAD_FILE")" = "$NEW" ] && exit 0

echo "New code found: ${OLD:0:7} -> ${NEW:0:7}"
if ! as_app git merge -q --ff-only "origin/$BRANCH"; then
    echo "ERROR: cannot fast-forward. Files were edited on the server; run 'git status' in $APP_DIR."
    exit 1
fi

restart_and_check() {
    if as_app git diff --quiet "$1" HEAD -- requirements.txt; then :; else
        as_app venv/bin/pip install -q -r requirements.txt
    fi
    systemctl restart "$SERVICE"
    for _ in $(seq 1 30); do
        [ "$(curl -s -o /dev/null -w '%{http_code}' "$HEALTH_URL" || true)" = "200" ] && return 0
        sleep 2
    done
    return 1
}

if restart_and_check "$OLD"; then
    echo "$NEW" > "$APP_DIR/.deployed_commit"
    echo "Deployed ${NEW:0:7} successfully."
    exit 0
fi

echo "ERROR: app not healthy after deploying ${NEW:0:7}. Rolling back to ${OLD:0:7}."
journalctl -u "$SERVICE" -n 40 --no-pager || true
as_app git reset -q --hard "$OLD"
if restart_and_check "$NEW"; then
    echo "$OLD" > "$APP_DIR/.deployed_commit"
    echo "Rolled back to ${OLD:0:7}. It will retry when a newer commit is pushed."
else
    echo "ERROR: app still unhealthy after rollback."
fi
# Remember the bad commit so we don't redeploy it every few minutes.
echo "$NEW" > "$BAD_FILE"
exit 1

#!/bin/bash
# poll_replies.sh — wait up to 90s for a bot reply (use after slow commands like /weat-draft)
#
# Usage:
#   ./spikes/S5-e2e/poll_replies.sh

# ── Same values as send_command.sh ───────────────────────────────────────────
HOMESERVER="http://localhost:8008"
TOKEN="syt_d2VhdF9hbGljZQ_czYWQonWskroRSanMtxA_2iyGl6"           # weat_alice's access token
WEAT_ROOM="!nCBykeBgXKeUPXFFaz:localhost"       # WeAt command room ID
# ─────────────────────────────────────────────────────────────────────────────

if [[ -z "$TOKEN" || -z "$WEAT_ROOM" ]]; then
  echo "ERROR: set TOKEN and WEAT_ROOM at the top of this script first"
  exit 1
fi

TIMEOUT=90
INTERVAL=3
ELAPSED=0
SENT_AFTER=$(date +%s)000   # ms timestamp — only show replies from after now

echo "Polling for bot reply (up to ${TIMEOUT}s)..."

while [[ $ELAPSED -lt $TIMEOUT ]]; do
  RESPONSE=$(curl -s \
    "$HOMESERVER/_matrix/client/v3/rooms/$WEAT_ROOM/messages?limit=10&dir=b" \
    -H "Authorization: Bearer $TOKEN")

  RESULT=$(echo "$RESPONSE" | python3 -c "
import sys, json
sent_after = $SENT_AFTER
data = json.loads(sys.stdin.read())
for e in reversed(data.get('chunk', [])):
    if e.get('type') != 'm.room.message':
        continue
    if e.get('origin_server_ts', 0) < sent_after:
        continue
    content = e.get('content', {})
    if content.get('dev.weat.bot'):
        print(content.get('body', ''))
        break
")

  if [[ -n "$RESULT" ]]; then
    echo "─── Bot reply ───"
    echo "$RESULT"
    echo "─────────────────"
    exit 0
  fi

  sleep $INTERVAL
  ELAPSED=$((ELAPSED + INTERVAL))
  echo -n "."
done

echo ""
echo "No reply after ${TIMEOUT}s. Check weat-bridge logs for errors."
exit 1

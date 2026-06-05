#!/bin/bash
# send_command.sh — send a WeAt command and print the bot's reply
#
# Usage:
#   ./spikes/S5-e2e/send_command.sh "/weat-help"
#   ./spikes/S5-e2e/send_command.sh "/weat-reply !abc123:localhost 回应一下 Redis 修复进展"
#   ./spikes/S5-e2e/send_command.sh "/weat-send"

# ── Fill these in once ────────────────────────────────────────────────────────
HOMESERVER="http://localhost:8008"
TOKEN="syt_d2VhdF9hbGljZQ_czYWQonWskroRSanMtxA_2iyGl6"           # weat_alice's access token (syt_d2VhdF9hbGljZQ_...)
WEAT_ROOM="!nCBykeBgXKeUPXFFaz:localhost"       # WeAt command room ID     (!xxx:localhost)
# ─────────────────────────────────────────────────────────────────────────────

set -e

if [[ -z "$TOKEN" || -z "$WEAT_ROOM" ]]; then
  echo "ERROR: set TOKEN and WEAT_ROOM at the top of this script first"
  exit 1
fi

COMMAND="${1:-/weat-help}"

# Capture send time before the request so poll_replies.sh can use it
SEND_TS=$(date +%s)000

# Send the command
TXN_ID="weat_$(date +%s%3N)"
curl -s -X PUT \
  "$HOMESERVER/_matrix/client/v3/rooms/$WEAT_ROOM/send/m.room.message/$TXN_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"msgtype\":\"m.text\",\"body\":$(echo -n "$COMMAND" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')}" \
  > /dev/null

echo "Sent: $COMMAND"
echo "Waiting for reply..."
sleep 2

# Poll for recent messages and print anything from the bot
RESPONSE=$(curl -s \
  "$HOMESERVER/_matrix/client/v3/rooms/$WEAT_ROOM/messages?limit=5&dir=b" \
  -H "Authorization: Bearer $TOKEN")

echo "$RESPONSE" | python3 -c "
import sys, json
data = json.loads(sys.stdin.read())
for e in reversed(data.get('chunk', [])):
    if e.get('type') != 'm.room.message':
        continue
    content = e.get('content', {})
    if content.get('dev.weat.bot'):
        print('─── Bot reply ───')
        print(content.get('body', ''))
        print('─────────────────')
        break
else:
    print('(no bot reply yet — for slow commands like /weat-draft, run ./poll_replies.sh to wait longer)')
"

echo "(tip: for slow commands, run: ./spikes/S5-e2e/poll_replies.sh $SEND_TS)"

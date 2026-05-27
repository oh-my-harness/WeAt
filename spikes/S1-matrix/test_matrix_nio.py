"""
S1 spike: verify Matrix REST API works with user token (no matrix-nio sync needed).

Get token from Element: All settings → Help & About → bottom → Access Token

Usage:
    MATRIX_USERNAME=@hhllhhyyds:matrix.org \
    MATRIX_TOKEN=mat_xxx \
    MATRIX_ROOM_ID='!xxx:matrix.org' \
    uv run python spikes/S1-matrix/test_matrix_nio.py
"""
import asyncio
import argparse
import os
import sys
import json
import aiohttp


async def run_spike(homeserver: str, user_id: str, token: str, room_id: str) -> bool:
    headers = {"Authorization": f"Bearer {token}"}

    async with aiohttp.ClientSession(headers=headers) as session:
        # 1. Verify token works (whoami)
        print(f"[S1] Verifying token ...")
        async with session.get(f"{homeserver}/_matrix/client/v3/account/whoami") as resp:
            if resp.status != 200:
                print(f"[S1] FAIL whoami: HTTP {resp.status} — {await resp.text()}")
                return False
            data = await resp.json()
            print(f"[S1] OK  logged in as {data.get('user_id')}")

        # 2. Read recent messages
        print(f"[S1] Fetching messages from {room_id} ...")
        url = f"{homeserver}/_matrix/client/v3/rooms/{room_id}/messages"
        async with session.get(url, params={"limit": 10, "dir": "b"}) as resp:
            if resp.status != 200:
                print(f"[S1] FAIL messages: HTTP {resp.status} — {await resp.text()}")
                return False
            data = await resp.json()
            msgs = [e for e in data.get("chunk", []) if e.get("type") == "m.room.message"]
            print(f"[S1] OK  got {len(msgs)} messages")
            for m in msgs[:3]:
                body = m.get("content", {}).get("body", "")
                print(f"       {m.get('sender')}: {body[:60]!r}")

        # 3. Send a test message as the user
        print(f"[S1] Sending test message as {user_id} ...")
        import time
        txn_id = str(int(time.time() * 1000))
        url = f"{homeserver}/_matrix/client/v3/rooms/{room_id}/send/m.room.message/{txn_id}"
        async with session.put(url, json={"msgtype": "m.text", "body": "[WeAt S1 spike] hello from matrix REST API"}) as resp:
            if resp.status != 200:
                print(f"[S1] FAIL send: HTTP {resp.status} — {await resp.text()}")
                return False
            data = await resp.json()
            print(f"[S1] OK  event_id={data.get('event_id')}")

    print("[S1] Check Element: message should show as sent by the user, no bot indicator.")
    print("[S1] PASS — D7 assumption verified ✅")
    return True


def main():
    homeserver = os.getenv("MATRIX_HOMESERVER", "https://matrix.org")
    user_id = os.getenv("MATRIX_USERNAME", "")
    token = os.getenv("MATRIX_TOKEN", "")
    room_id = os.getenv("MATRIX_ROOM_ID", "")

    if not user_id or not token or not room_id:
        print("需要: MATRIX_USERNAME, MATRIX_TOKEN, MATRIX_ROOM_ID")
        sys.exit(1)

    ok = asyncio.run(run_spike(homeserver, user_id, token, room_id))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

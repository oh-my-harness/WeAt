"""
S1 spike: verify matrix-nio can login, read history, and send as user identity.

Usage:
    uv run python spikes/S1-matrix/test_matrix_nio.py \
        --homeserver https://matrix.org \
        --username @alice:matrix.org \
        --password "..." \
        --room-id "!roomid:matrix.org"

Or set env vars: MATRIX_HOMESERVER, MATRIX_USERNAME, MATRIX_PASSWORD, MATRIX_ROOM_ID
"""
import asyncio
import argparse
import os
import sys
import json
import nio


async def run_spike(homeserver: str, username: str, password: str, room_id: str) -> bool:
    client = nio.AsyncClient(homeserver, username)

    print(f"[S1] Logging in as {username} ...")
    resp = await client.login(password)
    if isinstance(resp, nio.LoginError):
        print(f"[S1] FAIL login: {resp.message}")
        await client.close()
        return False
    print(f"[S1] OK  access_token={resp.access_token[:20]}...")

    print(f"[S1] Syncing to get room state ...")
    await client.sync(timeout=10000, full_state=True)

    print(f"[S1] Fetching last 10 messages from {room_id} ...")
    resp = await client.room_messages(
        room_id, start="", limit=10, direction=nio.MessageDirection.back
    )
    if isinstance(resp, nio.RoomMessagesError):
        print(f"[S1] FAIL room_messages: {resp.message}")
        await client.close()
        return False

    msgs = [
        e for e in resp.chunk if isinstance(e, nio.RoomMessageText)
    ]
    print(f"[S1] OK  got {len(msgs)} text messages (of {len(resp.chunk)} events)")
    for m in msgs[:3]:
        print(f"       {m.sender}: {m.body[:60]!r}")

    print(f"[S1] Sending test message as {username} ...")
    resp = await client.room_send(
        room_id,
        message_type="m.room.message",
        content={"msgtype": "m.text", "body": "[WeAt S1 spike] hello from matrix-nio"},
    )
    if isinstance(resp, nio.RoomSendError):
        print(f"[S1] FAIL send: {resp.message}")
        await client.close()
        return False
    print(f"[S1] OK  event_id={resp.event_id}")
    print("[S1] Check Element: the message should appear as sent by the user, no bot indicator.")

    await client.close()
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--homeserver", default=os.getenv("MATRIX_HOMESERVER", "https://matrix.org"))
    parser.add_argument("--username", default=os.getenv("MATRIX_USERNAME", ""))
    parser.add_argument("--password", default=os.getenv("MATRIX_PASSWORD", ""))
    parser.add_argument("--room-id", default=os.getenv("MATRIX_ROOM_ID", ""))
    args = parser.parse_args()

    if not args.username or not args.password or not args.room_id:
        print("Set MATRIX_USERNAME, MATRIX_PASSWORD, MATRIX_ROOM_ID env vars or pass CLI flags.")
        sys.exit(1)

    ok = asyncio.run(run_spike(args.homeserver, args.username, args.password, args.room_id))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

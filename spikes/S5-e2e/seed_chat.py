"""
seed_chat.py — seed a local Synapse instance with a mock dev-team conversation.

Reads dev_team_transcript.json, then for each user:
  1. Registers the account (skips if already exists, then logs in)
  2. Sets display name
  3. Creates/joins the group room
  4. Sends all their messages in transcript order using their own token

Messages are sent 200ms apart so Synapse stamps them with distinct timestamps.
The created room_id is printed at the end — paste it into weat.json or your test config.

Requirements:
  Synapse running on localhost:8008 with these options in homeserver.yaml:
    enable_registration: true
    enable_registration_without_verification: true

Usage:
    uv run python spikes/S5-e2e/seed_chat.py
    uv run python spikes/S5-e2e/seed_chat.py --homeserver http://localhost:8008
    uv run python spikes/S5-e2e/seed_chat.py --transcript path/to/transcript.json
    uv run python spikes/S5-e2e/seed_chat.py --homeserver http://localhost:8008 --transcript spikes/S5-e2e/dev_team_transcript.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import aiohttp

DEFAULT_HOMESERVER = "http://localhost:8008"
DEFAULT_TRANSCRIPT = Path(__file__).parent / "dev_team_transcript.json"


async def _post_with_retry(
    session: aiohttp.ClientSession,
    url: str,
    body: dict,
    label: str,
    max_attempts: int = 8,
) -> dict:
    """POST with automatic retry on M_LIMIT_EXCEEDED."""
    for attempt in range(max_attempts):
        async with session.post(url, json=body) as r:
            data = await r.json()
        if data.get("errcode") != "M_LIMIT_EXCEEDED":
            return data
        wait_ms = data.get("retry_after_ms", 5000)
        print(f"  [{label}] rate limited, waiting {wait_ms}ms ...")
        await asyncio.sleep(wait_ms / 1000 + 0.5)
    raise RuntimeError(f"still rate-limited after {max_attempts} attempts for {label}")


async def register_or_login(
    session: aiohttp.ClientSession,
    homeserver: str,
    localpart: str,
    password: str,
) -> str:
    """Return an access token for the user, registering first if needed."""
    url = f"{homeserver}/_matrix/client/v3/register"

    # Step 1: attempt registration (get auth session)
    data = await _post_with_retry(
        session, url,
        {"username": localpart, "password": password, "kind": "user"},
        localpart,
    )

    if "access_token" in data:
        return data["access_token"]

    if data.get("errcode") == "M_USER_IN_USE":
        print(f"  [{localpart}] already exists, logging in ...")
        return await _login(session, homeserver, localpart, password)

    # Step 2: complete dummy auth flow
    auth_session = data.get("session")
    if not auth_session:
        raise RuntimeError(f"register step 1 unexpected response for {localpart}: {data}")

    data = await _post_with_retry(
        session, url,
        {
            "username": localpart,
            "password": password,
            "kind": "user",
            "auth": {"type": "m.login.dummy", "session": auth_session},
        },
        localpart,
    )

    if "access_token" in data:
        return data["access_token"]

    if data.get("errcode") == "M_USER_IN_USE":
        print(f"  [{localpart}] already exists, logging in ...")
        return await _login(session, homeserver, localpart, password)

    raise RuntimeError(f"registration failed for {localpart}: {data}")


async def _login(
    session: aiohttp.ClientSession,
    homeserver: str,
    localpart: str,
    password: str,
) -> str:
    for attempt in range(5):
        async with session.post(f"{homeserver}/_matrix/client/v3/login", json={
            "type": "m.login.password",
            "user": localpart,
            "password": password,
        }) as r:
            data = await r.json()
        if "access_token" in data:
            return data["access_token"]
        if data.get("errcode") == "M_LIMIT_EXCEEDED":
            wait_ms = data.get("retry_after_ms", 3000)
            print(f"  [{localpart}] rate limited, waiting {wait_ms}ms ...")
            await asyncio.sleep(wait_ms / 1000 + 0.5)
            continue
        raise RuntimeError(f"login failed for {localpart}: {data}")
    raise RuntimeError(f"login still rate-limited after 5 attempts for {localpart}")


async def set_display_name(
    session: aiohttp.ClientSession,
    homeserver: str,
    user_id: str,
    token: str,
    display_name: str,
) -> None:
    url = f"{homeserver}/_matrix/client/v3/profile/{user_id}/displayname"
    async with session.put(url, headers={"Authorization": f"Bearer {token}"},
                           json={"displayname": display_name}) as r:
        if r.status not in (200, 204):
            print(f"  warning: could not set display name for {user_id}: {await r.text()}")


async def create_room(
    session: aiohttp.ClientSession,
    homeserver: str,
    token: str,
    name: str,
    topic: str,
    invite_ids: list[str],
) -> str:
    async with session.post(
        f"{homeserver}/_matrix/client/v3/createRoom",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": name,
            "topic": topic,
            "preset": "public_chat",
            "invite": invite_ids,
        },
    ) as r:
        data = await r.json()
    if "room_id" not in data:
        raise RuntimeError(f"createRoom failed: {data}")
    return data["room_id"]


async def join_room(
    session: aiohttp.ClientSession,
    homeserver: str,
    token: str,
    room_id: str,
) -> None:
    async with session.post(
        f"{homeserver}/_matrix/client/v3/join/{room_id}",
        headers={"Authorization": f"Bearer {token}"},
    ) as r:
        data = await r.json()
        if "errcode" in data and data["errcode"] not in ("M_ALREADY_IN_ROOM",):
            print(f"  warning: join failed: {data}")


async def send_message(
    session: aiohttp.ClientSession,
    homeserver: str,
    token: str,
    room_id: str,
    body: str,
) -> str:
    txn_id = f"weat_seed_{int(time.time() * 1000)}"
    url = f"{homeserver}/_matrix/client/v3/rooms/{room_id}/send/m.room.message/{txn_id}"
    async with session.put(
        url,
        headers={"Authorization": f"Bearer {token}"},
        json={"msgtype": "m.text", "body": body},
    ) as r:
        data = await r.json()
    return data.get("event_id", "")


async def check_synapse(homeserver: str) -> bool:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                f"{homeserver}/_matrix/client/versions",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as r:
                return r.status == 200
    except Exception:
        return False


async def seed(homeserver: str, transcript_path: Path) -> None:
    transcript = json.loads(transcript_path.read_text())
    room_cfg = transcript["room"]
    users_cfg = transcript["users"]
    messages_cfg = transcript["messages"]

    print(f"Checking Synapse at {homeserver} ...")
    if not await check_synapse(homeserver):
        print("ERROR: Synapse is not reachable. Start it first and re-run.")
        sys.exit(1)
    print("Synapse OK\n")

    domain = homeserver.split("://", 1)[-1].split(":")[0]  # e.g. "localhost"

    async with aiohttp.ClientSession() as session:
        # ── 1. Register / login all users ────────────────────────────────────
        print("=== Registering / logging in users ===")
        tokens: dict[str, str] = {}   # localpart → token
        matrix_ids: dict[str, str] = {}  # localpart → full @user:domain

        for u in users_cfg:
            lp = u["localpart"]
            print(f"  {lp} ({u['display_name']}) ...")
            token = await register_or_login(session, homeserver, lp, u["password"])
            tokens[lp] = token
            matrix_ids[lp] = f"@{lp}:{domain}"
            await set_display_name(session, homeserver, matrix_ids[lp], token, u["display_name"])
            print(f"    token: {token[:24]}...")

        # ── 2. Create room as first user, invite the rest ─────────────────
        print("\n=== Creating room ===")
        creator_lp = users_cfg[0]["localpart"]
        others = [matrix_ids[u["localpart"]] for u in users_cfg[1:]]
        room_id = await create_room(
            session,
            homeserver,
            tokens[creator_lp],
            room_cfg["name"],
            room_cfg["topic"],
            invite_ids=others,
        )
        print(f"  room_id: {room_id}")

        # ── 3. Have invited users join ────────────────────────────────────
        print("\n=== Joining room ===")
        for u in users_cfg[1:]:
            lp = u["localpart"]
            await join_room(session, homeserver, tokens[lp], room_id)
            print(f"  {lp} joined")

        # ── 4. Send messages in transcript order ──────────────────────────
        print(f"\n=== Sending {len(messages_cfg)} messages ===")
        unknown_senders: set[str] = set()
        for i, msg in enumerate(messages_cfg):
            sender_lp = msg["sender"]
            if sender_lp not in tokens:
                if sender_lp not in unknown_senders:
                    print(f"  WARNING: unknown sender '{sender_lp}' in message {i}, skipping")
                    unknown_senders.add(sender_lp)
                continue
            event_id = await send_message(
                session,
                homeserver,
                tokens[sender_lp],
                room_id,
                msg["body"],
            )
            label = f"[{msg['ts']}] {sender_lp}"
            print(f"  [{i+1:02d}/{len(messages_cfg)}] {label}: {msg['body'][:60]!r}")
            # 200ms gap so messages get distinct server timestamps
            await asyncio.sleep(0.2)

        # ── 5. Summary ───────────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("SEED COMPLETE")
        print("=" * 60)
        print(f"\nRoom:    {room_cfg['name']}")
        print(f"Room ID: {room_id}")
        print(f"Server:  {homeserver}\n")
        print("Users:")
        for u in users_cfg:
            lp = u["localpart"]
            print(f"  {matrix_ids[lp]!s:<35}  password: {u['password']}")
        print(f"\nAdd this room_id to your weat.json as the target room for testing:")
        print(f"  \"weat_room_id\": \"{room_id}\"")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a Synapse instance with a mock dev-team chat.")
    parser.add_argument("--homeserver", default=DEFAULT_HOMESERVER)
    parser.add_argument("--transcript", type=Path, default=DEFAULT_TRANSCRIPT)
    args = parser.parse_args()

    if not args.transcript.exists():
        print(f"ERROR: transcript not found at {args.transcript}")
        sys.exit(1)

    asyncio.run(seed(args.homeserver, args.transcript))


if __name__ == "__main__":
    main()

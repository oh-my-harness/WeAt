"""
Integration test: full WeAt workflow against local Synapse.

What this does:
1. Ensures Synapse is running on localhost:8008
2. Gets tokens for alice (user) and mybot (bot)
3. Creates a DM room (alice → mybot)
4. Creates a group room for drafting to
5. Starts weat-bridge in background
6. Sends /draft command as alice via Matrix REST API
7. Polls for bot reply
8. Sends /cancel to clean up

Run:
    uv run python spikes/S5-e2e/integration_test.py
"""
import asyncio
import json
import os
import signal
import subprocess
import sys
import time
import tempfile
import shutil

import aiohttp

SYNAPSE = "http://localhost:8008"


async def login(session: aiohttp.ClientSession, username: str, password: str) -> str:
    for attempt in range(5):
        async with session.post(f"{SYNAPSE}/_matrix/client/v3/login", json={
            "type": "m.login.password", "user": username, "password": password
        }) as r:
            data = await r.json()
            if "access_token" in data:
                return data["access_token"]
            if data.get("errcode") == "M_LIMIT_EXCEEDED":
                wait_ms = data.get("retry_after_ms", 5000)
                await asyncio.sleep(wait_ms / 1000 + 1)
                continue
            raise RuntimeError(f"Login failed for {username}: {data}")
    raise RuntimeError(f"Login still rate-limited after 5 attempts for {username}")


async def create_room(session: aiohttp.ClientSession, token: str, name: str) -> str:
    async with session.post(f"{SYNAPSE}/_matrix/client/v3/createRoom",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "preset": "public_chat"}
    ) as r:
        data = await r.json()
        return data["room_id"]


async def create_dm(session: aiohttp.ClientSession, token: str, other_user_id: str) -> str:
    async with session.post(f"{SYNAPSE}/_matrix/client/v3/createRoom",
        headers={"Authorization": f"Bearer {token}"},
        json={"preset": "trusted_private_chat", "invite": [other_user_id],
              "is_direct": True}
    ) as r:
        data = await r.json()
        return data["room_id"]


async def join_room(session: aiohttp.ClientSession, token: str, room_id: str) -> None:
    async with session.post(f"{SYNAPSE}/_matrix/client/v3/join/{room_id}",
        headers={"Authorization": f"Bearer {token}"}
    ) as r:
        await r.json()


async def send_message(session: aiohttp.ClientSession, token: str, room_id: str, text: str) -> str:
    txn = str(int(time.time() * 1000))
    async with session.put(
        f"{SYNAPSE}/_matrix/client/v3/rooms/{room_id}/send/m.room.message/{txn}",
        headers={"Authorization": f"Bearer {token}"},
        json={"msgtype": "m.text", "body": text}
    ) as r:
        data = await r.json()
        return data.get("event_id", "")


async def poll_messages(session: aiohttp.ClientSession, token: str, room_id: str,
                        after_ts: float, timeout: float = 30.0) -> list[dict]:
    """Poll for new messages from bot sent after after_ts (unix ms)."""
    deadline = time.time() + timeout
    seen = set()
    results = []
    while time.time() < deadline:
        async with session.get(
            f"{SYNAPSE}/_matrix/client/v3/rooms/{room_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
            params={"limit": 20, "dir": "b"}
        ) as r:
            data = await r.json()
        for e in data.get("chunk", []):
            ts = e.get("origin_server_ts", 0)
            if (e.get("type") == "m.room.message"
                    and e.get("event_id") not in seen
                    and e.get("sender") == "@mybot:localhost"
                    and ts > after_ts):
                seen.add(e["event_id"])
                results.append(e)
        if results:
            return results
        await asyncio.sleep(2)
    return []


async def check_synapse() -> bool:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{SYNAPSE}/_matrix/client/versions", timeout=aiohttp.ClientTimeout(total=3)) as r:
                return r.status == 200
    except Exception:
        return False


def start_synapse() -> subprocess.Popen:
    print("[test] Starting local Synapse ...")
    proc = subprocess.Popen(
        ["uv", "run", "python3", "-m", "synapse.app.homeserver",
         "--config-path", "/tmp/synapse-test/homeserver.yaml"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    return proc


async def main():
    print("=== WeAt Integration Test ===\n")

    # 1. Synapse
    synapse_proc = None
    if not await check_synapse():
        synapse_proc = start_synapse()
        for _ in range(10):
            await asyncio.sleep(2)
            if await check_synapse():
                print("[test] Synapse up")
                break
        else:
            print("[test] FAIL — Synapse did not start")
            sys.exit(1)
    else:
        print("[test] Synapse already running ✓")

    async with aiohttp.ClientSession() as session:
        # 2. Login (or use cached tokens from env)
        print("[test] Logging in ...")
        alice_token = os.environ.get("ALICE_TOKEN") or await login(session, "alice", "alice123")
        bot_token   = os.environ.get("BOT_TOKEN")   or await login(session, "mybot",  "bot123")
        print(f"       alice token: {alice_token[:25]}...")
        print(f"       bot   token: {bot_token[:25]}...")

        # 3. Create group room (draft target)
        group_room = await create_room(session, alice_token, "dev-team")
        print(f"[test] Group room: {group_room}")

        # 4. Create DM (alice → mybot)
        dm_room = await create_dm(session, alice_token, "@mybot:localhost")
        await join_room(session, bot_token, dm_room)
        print(f"[test] DM room:    {dm_room}")

        # 5. Write weat.json
        vault = tempfile.mkdtemp(prefix="weat-test-vault-")
        config = {
            "homeserver": SYNAPSE,
            "user_id": "@alice:localhost",
            "access_token": alice_token,
            "bot_user_id": "@mybot:localhost",
            "bot_access_token": bot_token,
            "vault_path": vault,
            "db_path": "/tmp/weat-test.db",
            "opencode_model": "opencode/deepseek-v4-flash-free",
            "session_timeout_minutes": 30,
        }
        config_path = "/tmp/weat-test.json"
        with open(config_path, "w") as f:
            json.dump(config, f)
        print(f"[test] Config written to {config_path}")

        # 6. Start weat-bridge
        print("[test] Starting weat-bridge ...")
        bridge = subprocess.Popen(
            ["uv", "run", "weat-bridge", "--config", config_path, "--log-level", "DEBUG"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        await asyncio.sleep(6)   # wait for bot to connect and sync
        if bridge.poll() is not None:
            out, err = bridge.communicate()
            print(f"[test] FAIL — bridge exited early:\n{err.decode()[:1000]}")
            sys.exit(1)
        print("[test] Bridge running ✓")

        # 7. Send /help
        print("\n[test] Sending /help ...")
        ts_before_help = int(time.time() * 1000)
        await send_message(session, alice_token, dm_room, "/help")
        replies = await poll_messages(session, alice_token, dm_room, ts_before_help, timeout=20)
        if replies:
            print(f"[test] OK  bot replied to /help:")
            print(f"       {replies[0]['content']['body'][:120]}")
        else:
            print("[test] WARN — no /help reply within 20s (bot may still be syncing)")

        # 8. Send /draft
        print(f"\n[test] Sending /draft {group_room} hello world ...")
        ts_before_draft = int(time.time() * 1000)
        await send_message(
            session, alice_token, dm_room,
            f"/draft {group_room} write a one-sentence greeting"
        )
        print("[test] Waiting for draft reply (up to 60s, opencode LLM call) ...")
        replies = await poll_messages(session, alice_token, dm_room, ts_before_draft, timeout=60)
        if replies:
            body = replies[0]['content']['body']
            print(f"[test] OK  bot replied with draft:")
            print(f"       {body[:200]}")
        else:
            print("[test] WARN — no draft reply (check opencode LLM config)")

        # 9. Send /cancel
        await send_message(session, alice_token, dm_room, "/cancel")
        print("\n[test] /cancel sent")

        # 10. Verify /send posts to group room as alice
        if replies:
            print(f"\n[test] Testing /send — posting to group room as alice ...")
            ts_before_send_draft = int(time.time() * 1000)
            await send_message(session, alice_token, dm_room,
                               f"/draft {group_room} say: integration test message")
            await asyncio.sleep(3)
            # wait for ⏳ message then send
            await asyncio.sleep(30)   # give opencode time to generate
            ts_before_send = int(time.time() * 1000)
            await send_message(session, alice_token, dm_room, "/send")
            await asyncio.sleep(5)
            # Check group room for alice's message
            async with session.get(
                f"{SYNAPSE}/_matrix/client/v3/rooms/{group_room}/messages",
                headers={"Authorization": f"Bearer {alice_token}"},
                params={"limit": 5, "dir": "b"}
            ) as r:
                data = await r.json()
            alice_msgs = [e for e in data.get("chunk", [])
                          if e.get("sender") == "@alice:localhost"
                          and e.get("type") == "m.room.message"]
            if alice_msgs:
                print(f"[test] OK  /send posted to group room as @alice:localhost ✅")
                print(f"       {alice_msgs[0]['content']['body'][:100]}")
            else:
                print("[test] WARN — no alice message in group room yet")

    # Cleanup
    bridge.terminate()
    bridge.wait()
    shutil.rmtree(vault, ignore_errors=True)
    if synapse_proc:
        synapse_proc.terminate()

    print("\n=== Integration test complete ===")


if __name__ == "__main__":
    asyncio.run(main())

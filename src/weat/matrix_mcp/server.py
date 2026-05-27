"""
Matrix MCP Server — exposes Matrix room data to opencode agents as MCP tools.

Uses Matrix REST API directly (via aiohttp) to avoid matrix-nio's sync requirement.

Tools exposed:
  - list_rooms()                              → rooms the bot/user has joined
  - get_recent_messages(room_id, limit=50)   → last N messages in a room
  - search_messages(room_id, query, limit=20) → keyword search in room timeline

Intentionally NOT exposed: send_message — sending always goes through the
orchestrator's human-review loop, never directly from the agent.

Transport: stdio (started by the orchestrator as a subprocess).
Config via env vars:
  WEAT_MATRIX_HOMESERVER   e.g. http://localhost:8008
  WEAT_MATRIX_ACCESS_TOKEN user's Matrix access token
  WEAT_MATRIX_USER_ID      e.g. @alice:localhost
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

import aiohttp
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("weat-matrix")


def _cfg() -> tuple[str, str]:
    return os.environ["WEAT_MATRIX_HOMESERVER"], os.environ["WEAT_MATRIX_ACCESS_TOKEN"]


def _headers() -> dict[str, str]:
    _, token = _cfg()
    return {"Authorization": f"Bearer {token}"}


def _fmt_event(e: dict, room_id: str) -> dict[str, Any]:
    ts = e.get("origin_server_ts")
    dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat() if ts else "unknown"
    return {
        "event_id": e.get("event_id", ""),
        "sender": e.get("sender", ""),
        "timestamp": dt,
        "body": e.get("content", {}).get("body", ""),
        "room_id": room_id,
    }


@mcp.tool()
async def list_rooms() -> str:
    """List all Matrix rooms the user has joined, with display names and IDs."""
    homeserver, _ = _cfg()
    async with aiohttp.ClientSession(headers=_headers(), trust_env=True) as s:
        async with s.get(f"{homeserver}/_matrix/client/v3/joined_rooms") as r:
            if r.status != 200:
                return json.dumps({"error": await r.text()})
            data = await r.json()

    rooms = []
    for room_id in data.get("joined_rooms", []):
        rooms.append({"room_id": room_id})
    return json.dumps(rooms, ensure_ascii=False)


@mcp.tool()
async def get_recent_messages(room_id: str, limit: int = 50) -> str:
    """
    Return the last `limit` text messages from a Matrix room.

    Args:
        room_id: Matrix room ID (e.g. '!abc123:localhost')
        limit:   Number of messages to retrieve (default 50, max 200)
    """
    limit = min(max(1, limit), 200)
    homeserver, _ = _cfg()
    async with aiohttp.ClientSession(headers=_headers(), trust_env=True) as s:
        url = f"{homeserver}/_matrix/client/v3/rooms/{room_id}/messages"
        async with s.get(url, params={"limit": limit, "dir": "b"}) as r:
            if r.status != 200:
                return json.dumps({"error": await r.text()})
            data = await r.json()

    msgs = [
        _fmt_event(e, room_id)
        for e in reversed(data.get("chunk", []))
        if e.get("type") == "m.room.message"
        and e.get("content", {}).get("msgtype") == "m.text"
    ]
    return json.dumps(msgs, ensure_ascii=False)


@mcp.tool()
async def search_messages(room_id: str, query: str, limit: int = 20) -> str:
    """
    Keyword search across recent messages in a Matrix room (client-side filter).

    Args:
        room_id: Matrix room ID
        query:   Search string (case-insensitive substring match)
        limit:   Max results to return (default 20)
    """
    limit = min(max(1, limit), 100)
    homeserver, _ = _cfg()
    async with aiohttp.ClientSession(headers=_headers(), trust_env=True) as s:
        url = f"{homeserver}/_matrix/client/v3/rooms/{room_id}/messages"
        async with s.get(url, params={"limit": 500, "dir": "b"}) as r:
            if r.status != 200:
                return json.dumps({"error": await r.text()})
            data = await r.json()

    q = query.lower()
    matches = [
        _fmt_event(e, room_id)
        for e in data.get("chunk", [])
        if e.get("type") == "m.room.message"
        and q in e.get("content", {}).get("body", "").lower()
    ][:limit]

    return json.dumps(
        {"query": query, "room_id": room_id, "count": len(matches), "results": matches},
        ensure_ascii=False,
    )


def main() -> None:
    required = ("WEAT_MATRIX_HOMESERVER", "WEAT_MATRIX_USER_ID", "WEAT_MATRIX_ACCESS_TOKEN")
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        print(f"Missing env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

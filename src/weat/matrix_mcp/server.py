"""
Matrix MCP Server — exposes Matrix room data to opencode agents as MCP tools.

Tools exposed:
  - list_rooms()                              → rooms the bot has joined
  - get_recent_messages(room_id, limit=50)   → last N messages in a room
  - search_messages(room_id, query, limit=20) → keyword search in room timeline

Intentionally NOT exposed: send_message — sending always goes through the
orchestrator's human-review loop, never directly from the agent.

Transport: stdio (started by the orchestrator as a subprocess).
Config via env vars:
  WEAT_MATRIX_HOMESERVER   e.g. https://matrix.org
  WEAT_MATRIX_ACCESS_TOKEN user's Matrix access token
  WEAT_MATRIX_USER_ID      e.g. @alice:matrix.org
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

import nio
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("weat-matrix")

_client: nio.AsyncClient | None = None
_sync_done = asyncio.Event()


def _make_client() -> nio.AsyncClient:
    homeserver = os.environ["WEAT_MATRIX_HOMESERVER"]
    user_id = os.environ["WEAT_MATRIX_USER_ID"]
    access_token = os.environ["WEAT_MATRIX_ACCESS_TOKEN"]

    client = nio.AsyncClient(homeserver, user_id)
    client.access_token = access_token
    client.user_id = user_id
    return client


async def _ensure_synced() -> nio.AsyncClient:
    global _client
    if _client is None:
        _client = _make_client()
        resp = await _client.sync(timeout=15000, full_state=True)
        if isinstance(resp, nio.SyncError):
            raise RuntimeError(f"Matrix sync failed: {resp.message}")
    return _client


def _format_message(event: nio.RoomMessageText | nio.RoomEncryptedText, room_id: str) -> dict[str, Any]:
    ts = getattr(event, "server_timestamp", None)
    dt = (
        datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()
        if ts
        else "unknown"
    )
    return {
        "event_id": event.event_id,
        "sender": event.sender,
        "timestamp": dt,
        "body": getattr(event, "body", "[encrypted]"),
        "room_id": room_id,
    }


@mcp.tool()
async def list_rooms() -> str:
    """List all Matrix rooms the bot/user has joined, with display names and IDs."""
    client = await _ensure_synced()
    rooms = []
    for room_id, room in client.rooms.items():
        rooms.append({
            "room_id": room_id,
            "display_name": room.display_name or room_id,
            "member_count": room.member_count,
        })
    return json.dumps(rooms, ensure_ascii=False)


@mcp.tool()
async def get_recent_messages(room_id: str, limit: int = 50) -> str:
    """
    Return the last `limit` text messages from a Matrix room.

    Args:
        room_id: Matrix room ID (e.g. '!abc123:matrix.org' or display name)
        limit:   Number of messages to retrieve (default 50, max 200)
    """
    limit = min(max(1, limit), 200)
    client = await _ensure_synced()

    # Accept either room_id or display name
    resolved = _resolve_room(client, room_id)
    if not resolved:
        return json.dumps({"error": f"Room not found: {room_id!r}"})

    resp = await client.room_messages(
        resolved,
        start="",
        limit=limit,
        direction=nio.MessageDirection.back,
    )
    if isinstance(resp, nio.RoomMessagesError):
        return json.dumps({"error": resp.message})

    messages = [
        _format_message(e, resolved)
        for e in reversed(resp.chunk)
        if isinstance(e, (nio.RoomMessageText,))
    ]
    return json.dumps(messages, ensure_ascii=False)


@mcp.tool()
async def search_messages(room_id: str, query: str, limit: int = 20) -> str:
    """
    Keyword search across recent messages in a Matrix room (client-side filter).

    Args:
        room_id: Matrix room ID or display name
        query:   Search string (case-insensitive substring match)
        limit:   Max results to return (default 20)
    """
    limit = min(max(1, limit), 100)
    client = await _ensure_synced()

    resolved = _resolve_room(client, room_id)
    if not resolved:
        return json.dumps({"error": f"Room not found: {room_id!r}"})

    # Fetch a larger window to search through
    resp = await client.room_messages(
        resolved,
        start="",
        limit=500,
        direction=nio.MessageDirection.back,
    )
    if isinstance(resp, nio.RoomMessagesError):
        return json.dumps({"error": resp.message})

    q = query.lower()
    matches = [
        _format_message(e, resolved)
        for e in resp.chunk
        if isinstance(e, nio.RoomMessageText) and q in e.body.lower()
    ][:limit]

    return json.dumps(
        {"query": query, "room_id": resolved, "count": len(matches), "results": matches},
        ensure_ascii=False,
    )


def _resolve_room(client: nio.AsyncClient, room_ref: str) -> str | None:
    """Resolve room display name or ID to a canonical room_id."""
    if room_ref in client.rooms:
        return room_ref
    # Try stripping leading '#' shorthand
    for rid, room in client.rooms.items():
        if room.display_name == room_ref or room.display_name == room_ref.lstrip("#"):
            return rid
    return None


def main() -> None:
    required = ("WEAT_MATRIX_HOMESERVER", "WEAT_MATRIX_USER_ID", "WEAT_MATRIX_ACCESS_TOKEN")
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        print(f"Missing env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

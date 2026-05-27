"""
SQLite-backed session store for draft conversations.

Each session tracks:
  - user_id, room_id (target channel), draft text, conversation history
  - created_at, last_active_at, status (active | sent | saved | cancelled)
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import aiosqlite


class SessionStatus(str, Enum):
    ACTIVE = "active"
    SENT = "sent"
    SAVED = "saved"
    CANCELLED = "cancelled"


@dataclass
class DraftSession:
    id: int
    user_id: str
    target_room_id: str
    command_type: str          # "draft" or "digest"
    draft_text: str
    conversation_history: list[dict[str, str]]
    status: SessionStatus
    created_at: float
    last_active_at: float
    opencode_session_id: str   # opencode --session ID for multi-turn continuation

    @property
    def is_expired(self) -> bool:
        return time.time() - self.last_active_at > 30 * 60

    def to_db_row(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "target_room_id": self.target_room_id,
            "command_type": self.command_type,
            "draft_text": self.draft_text,
            "conversation_history": json.dumps(self.conversation_history, ensure_ascii=False),
            "status": self.status.value,
            "created_at": self.created_at,
            "last_active_at": self.last_active_at,
            "opencode_session_id": self.opencode_session_id,
        }


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS draft_sessions (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id              TEXT NOT NULL,
    target_room_id       TEXT NOT NULL,
    command_type         TEXT NOT NULL DEFAULT 'draft',
    draft_text           TEXT NOT NULL DEFAULT '',
    conversation_history TEXT NOT NULL DEFAULT '[]',
    status               TEXT NOT NULL DEFAULT 'active',
    created_at           REAL NOT NULL,
    last_active_at       REAL NOT NULL,
    opencode_session_id  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sent_drafts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    INTEGER NOT NULL,
    user_id       TEXT NOT NULL,
    target_room_id TEXT NOT NULL,
    final_text    TEXT NOT NULL,
    sent_at       REAL NOT NULL,
    event_id      TEXT NOT NULL DEFAULT ''
);
"""


class SessionStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def init(self) -> None:
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(CREATE_TABLE_SQL)
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    async def get_active_session(self, user_id: str) -> DraftSession | None:
        async with self._db.execute(
            "SELECT * FROM draft_sessions WHERE user_id=? AND status='active' ORDER BY last_active_at DESC LIMIT 1",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_session(dict(row))

    async def create_session(
        self,
        user_id: str,
        target_room_id: str,
        command_type: str = "draft",
    ) -> DraftSession:
        now = time.time()
        async with self._db.execute(
            """INSERT INTO draft_sessions
               (user_id, target_room_id, command_type, draft_text, conversation_history,
                status, created_at, last_active_at, opencode_session_id)
               VALUES (?, ?, ?, '', '[]', 'active', ?, ?, '')""",
            (user_id, target_room_id, command_type, now, now),
        ) as cursor:
            session_id = cursor.lastrowid
        await self._db.commit()
        return DraftSession(
            id=session_id,
            user_id=user_id,
            target_room_id=target_room_id,
            command_type=command_type,
            draft_text="",
            conversation_history=[],
            status=SessionStatus.ACTIVE,
            created_at=now,
            last_active_at=now,
            opencode_session_id="",
        )

    async def update_session(self, session: DraftSession) -> None:
        session.last_active_at = time.time()
        row = session.to_db_row()
        await self._db.execute(
            """UPDATE draft_sessions SET
               draft_text=:draft_text,
               conversation_history=:conversation_history,
               status=:status,
               last_active_at=:last_active_at,
               opencode_session_id=:opencode_session_id
               WHERE id=?""",
            (*[row[k] for k in ("draft_text", "conversation_history", "status",
                                "last_active_at", "opencode_session_id")], session.id),
        )
        await self._db.commit()

    async def cancel_active_session(self, user_id: str) -> bool:
        cur = await self._db.execute(
            "UPDATE draft_sessions SET status='cancelled' WHERE user_id=? AND status='active'",
            (user_id,),
        )
        await self._db.commit()
        return cur.rowcount > 0

    async def record_sent(
        self,
        session: DraftSession,
        final_text: str,
        event_id: str = "",
    ) -> None:
        await self._db.execute(
            """INSERT INTO sent_drafts (session_id, user_id, target_room_id, final_text, sent_at, event_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session.id, session.user_id, session.target_room_id, final_text, time.time(), event_id),
        )
        await self._db.commit()

    async def expire_stale_sessions(self, timeout_minutes: int = 30) -> int:
        cutoff = time.time() - timeout_minutes * 60
        cur = await self._db.execute(
            "UPDATE draft_sessions SET status='cancelled' WHERE status='active' AND last_active_at < ?",
            (cutoff,),
        )
        await self._db.commit()
        return cur.rowcount

    @staticmethod
    def _row_to_session(row: dict) -> DraftSession:
        return DraftSession(
            id=row["id"],
            user_id=row["user_id"],
            target_room_id=row["target_room_id"],
            command_type=row["command_type"],
            draft_text=row["draft_text"],
            conversation_history=json.loads(row["conversation_history"]),
            status=SessionStatus(row["status"]),
            created_at=row["created_at"],
            last_active_at=row["last_active_at"],
            opencode_session_id=row["opencode_session_id"],
        )

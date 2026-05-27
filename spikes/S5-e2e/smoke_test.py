"""
S5 smoke test: verifies the full skeleton works end-to-end WITHOUT a real Matrix server.

Tests:
1. Config loads from env vars
2. SessionStore creates / updates / expires sessions
3. OpenCodeRunner can call opencode and parse output
4. Orchestrator command parsing dispatches correctly (mocked Matrix client)

Run:
    uv run python spikes/S5-e2e/smoke_test.py
"""
import asyncio
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure src/ is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from weat.config.settings import Config
from weat.orchestrator.session_store import DraftSession, SessionStatus, SessionStore
from weat.orchestrator.opencode_runner import OpenCodeRunner


# ── Test 1: Config ────────────────────────────────────────────────────────────

def test_config_from_env():
    os.environ.update({
        "WEAT_MATRIX_HOMESERVER": "https://test.matrix.org",
        "WEAT_MATRIX_USER_ID": "@alice:test.matrix.org",
        "WEAT_MATRIX_ACCESS_TOKEN": "syt_token_alice",
        "WEAT_BOT_USER_ID": "@bot:test.matrix.org",
        "WEAT_BOT_ACCESS_TOKEN": "syt_token_bot",
        "WEAT_VAULT_PATH": "/tmp/test-vault",
    })
    cfg = Config.from_env()
    assert cfg.homeserver == "https://test.matrix.org"
    assert cfg.user_id == "@alice:test.matrix.org"
    assert cfg.vault_path == "/tmp/test-vault"
    errors = cfg.validate()
    assert errors == [], f"Unexpected errors: {errors}"
    print("[S5] OK  Config.from_env + validate")


# ── Test 2: SessionStore ─────────────────────────────────────────────────────

async def test_session_store():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=True) as f:
        db_path = f.name

    store = SessionStore(db_path)
    await store.init()

    # Create session
    session = await store.create_session("@alice:test", "!room123:test", "draft")
    assert session.id is not None
    assert session.status == SessionStatus.ACTIVE

    # Update draft
    session.draft_text = "Hello, this is the draft."
    session.opencode_session_id = "ses_abc123"
    await store.update_session(session)

    # Retrieve
    retrieved = await store.get_active_session("@alice:test")
    assert retrieved is not None
    assert retrieved.draft_text == "Hello, this is the draft."
    assert retrieved.opencode_session_id == "ses_abc123"

    # Cancel
    cancelled = await store.cancel_active_session("@alice:test")
    assert cancelled is True
    gone = await store.get_active_session("@alice:test")
    assert gone is None

    # Expiry
    session2 = await store.create_session("@bob:test", "!room456:test", "digest")
    # Manually set last_active_at to 2 hours ago
    import aiosqlite
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE draft_sessions SET last_active_at=? WHERE id=?",
            (time.time() - 7200, session2.id),
        )
        await db.commit()

    expired_count = await store.expire_stale_sessions(timeout_minutes=30)
    assert expired_count == 1

    await store.close()
    print("[S5] OK  SessionStore create/update/cancel/expire")


# ── Test 3: OpenCodeRunner parse ─────────────────────────────────────────────

def test_opencode_runner_parse():
    import json
    sample_output = "\n".join([
        json.dumps({"type": "step_start", "sessionID": "ses_xyz789", "part": {}}),
        json.dumps({"type": "text", "sessionID": "ses_xyz789", "part": {"text": "Hello ", "type": "text"}}),
        json.dumps({"type": "text", "sessionID": "ses_xyz789", "part": {"text": "world!", "type": "text"}}),
        json.dumps({"type": "step_finish", "sessionID": "ses_xyz789", "part": {}}),
    ])
    text, sid = OpenCodeRunner._parse_output(sample_output)
    assert text == "Hello world!", f"Got: {text!r}"
    assert sid == "ses_xyz789", f"Got: {sid!r}"
    print("[S5] OK  OpenCodeRunner._parse_output")


# ── Test 4: Orchestrator command dispatch ─────────────────────────────────────

async def test_orchestrator_dispatch():
    from weat.orchestrator.orchestrator import Orchestrator
    import nio

    cfg = Config.from_env()
    with tempfile.NamedTemporaryFile(suffix=".db", delete=True) as f:
        cfg.db_path = f.name
    cfg.vault_path = tempfile.mkdtemp()

    orch = Orchestrator(cfg)
    await orch.store.init()

    sent_messages = []

    async def mock_send_bot(room_id, text):
        sent_messages.append(text)

    async def mock_run(prompt, session_id=None):
        return "Draft v1: Redis is cool.", "ses_fake"

    orch._send_bot_message = mock_send_bot
    orch.runner.run = mock_run

    # Dispatch /help
    await orch._dispatch("!dm:test", "@alice:test", "/help")
    assert any("WeAt" in m for m in sent_messages), "Help text not sent"
    sent_messages.clear()

    # Dispatch /draft (will call runner.run)
    orch._user_client = MagicMock()
    await orch._dispatch("!dm:test", "@alice:test", "/draft #dev-team explain the P1 fix")
    # Should send a "generating..." message + draft reply
    assert any("草稿 v1" in m or "⏳" in m or "Redis" in m for m in sent_messages), \
        f"Draft not sent: {sent_messages}"
    sent_messages.clear()

    # Dispatch refinement (non-command text with active session)
    await orch._dispatch("!dm:test", "@alice:test", "太长了，缩短到一句话")
    assert any("草稿" in m or "修改" in m or "Redis" in m or "⏳" in m for m in sent_messages), \
        f"Refinement not handled: {sent_messages}"

    # Dispatch /cancel
    sent_messages.clear()
    await orch._dispatch("!dm:test", "@alice:test", "/cancel")
    assert any("取消" in m for m in sent_messages), f"Cancel not confirmed: {sent_messages}"

    await orch.store.close()
    print("[S5] OK  Orchestrator dispatch: /help /draft refinement /cancel")


# ── Runner ────────────────────────────────────────────────────────────────────

async def main():
    print("=== S5 End-to-End Smoke Test ===\n")
    test_config_from_env()
    await test_session_store()
    test_opencode_runner_parse()
    await test_orchestrator_dispatch()
    print("\n[S5] ALL PASS ✅")


if __name__ == "__main__":
    asyncio.run(main())

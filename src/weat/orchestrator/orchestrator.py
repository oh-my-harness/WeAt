"""
Orchestrator — listens to the bot's private DMs and drives the draft workflow.

State machine per user:
  idle ──[/draft or /digest]──► active (generating draft)
  active ──[refinement text]──► active (refining)
  active ──[/retry]──────────► active (regenerating)
  active ──[/send]────────────► sent   (message delivered as user)
  active ──[/save]────────────► saved  (note written to vault)
  active ──[/cancel]──────────► cancelled

The bot listens on its own account (@BotName) for DMs from the user.
Sends are made with the USER's access token, not the bot's.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from typing import Callable, Awaitable

import nio

from ..config.settings import Config
from .session_store import DraftSession, SessionStatus, SessionStore
from .opencode_runner import OpenCodeRunner

logger = logging.getLogger(__name__)

HELP_TEXT = """\
**WeAt AI 副驾驶** — 命令列表：

📝 **起草回复**
`/draft <频道> <主题>`  — 起草一条回复（如 `/draft #开发组 解释上周的 P1`）

📋 **总结群聊**
`/digest <频道> <时间范围>` — 生成纪要草稿（如 `/digest #开发组 本周`）

✅ **操作草稿**
`/send`   — 以你的身份发到目标频道
`/save`   — 保存为 Obsidian 笔记
`/retry`  — 重新生成当前草稿
`/cancel` — 放弃当前草稿
`/help`   — 显示此帮助

💬 **直接说要怎么改** — 非命令消息默认为对当前草稿的改稿指令。
"""

DRAFT_SYSTEM_PROMPT = """\
你是用户的私人 AI 副驾驶，帮助起草 Matrix 群聊回复。

任务：根据群聊历史和用户的个人知识库（vault），起草一条清晰、自然的回复。

输出格式：
1. 直接给出草稿正文（不要加"草稿："前缀）
2. 在草稿后空一行，列出引用来源（格式：📚 引用：[[笔记名]] / 群聊 发言人 时间）
3. 在引用后空一行，用一句话描述你的步骤（格式：🤖 步骤：...）

语气：和用户平时发言风格一致，自然、专业，不要过于正式。
"""

DIGEST_SYSTEM_PROMPT = """\
你是用户的私人 AI 副驾驶，帮助整理群聊纪要。

任务：根据指定时间段的群聊内容，生成结构化的纪要草稿，供用户保存到 Obsidian 知识库。

输出格式：请遵循 vault 的 AI-first 规范（AGENTS.md 里有详细说明）：
- 包含 frontmatter（type、date、tags、ai-first: true）
- 包含 `## For future Claude` preamble
- 使用 [[wikilinks]] 引用人物和项目

直接输出 markdown 文档内容，不要加任何解释。
"""


class Orchestrator:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.store = SessionStore(config.db_path)
        self.runner = OpenCodeRunner(
            vault_path=config.vault_path,
            model=config.opencode_model,
        )
        self._bot_client: nio.AsyncClient | None = None
        self._user_client: nio.AsyncClient | None = None
        self._running = False

    async def start(self) -> None:
        await self.store.init()

        self._bot_client = nio.AsyncClient(self.config.homeserver, self.config.bot_user_id)
        self._bot_client.access_token = self.config.bot_access_token
        self._bot_client.user_id = self.config.bot_user_id

        self._user_client = nio.AsyncClient(self.config.homeserver, self.config.user_id)
        self._user_client.access_token = self.config.access_token
        self._user_client.user_id = self.config.user_id

        # Write opencode MCP config so agent can access Matrix rooms
        self.runner.write_opencode_config(
            homeserver=self.config.homeserver,
            user_id=self.config.user_id,
            access_token=self.config.access_token,
        )

        self._bot_client.add_event_callback(self._on_message, nio.RoomMessageText)
        self._running = True

        logger.info("Starting bot sync loop ...")
        first_sync = True
        while self._running:
            resp = await self._bot_client.sync(
                timeout=30000,
                full_state=first_sync,
                since=self._bot_client.next_batch if not first_sync else None,
            )
            first_sync = False
            if isinstance(resp, nio.SyncError):
                logger.error("Sync error: %s", resp.message)
                await asyncio.sleep(5)
                continue
            # Expire stale sessions periodically
            expired = await self.store.expire_stale_sessions(self.config.session_timeout_minutes)
            if expired:
                logger.info("Expired %d stale sessions", expired)

    async def stop(self) -> None:
        self._running = False
        if self._bot_client:
            await self._bot_client.close()
        if self._user_client:
            await self._user_client.close()
        await self.store.close()

    async def _on_message(self, room: nio.MatrixRoom, event: nio.RoomMessageText) -> None:
        # Only handle DMs sent to the bot (ignore the bot's own messages)
        if event.sender == self.config.bot_user_id:
            return
        # Only handle messages from the configured user
        if event.sender != self.config.user_id:
            return
        # Only handle private DMs; member_count may be 0 before full sync,
        # so only skip when it's definitively > 2.
        if room.member_count and room.member_count > 2:
            return

        text = event.body.strip()
        user_id = event.sender
        room_id = room.room_id

        try:
            await self._dispatch(room_id, user_id, text)
        except Exception:
            logger.exception("Error handling message from %s", user_id)
            await self._send_bot_message(room_id, "❌ 出错了，请稍后再试或发 `/cancel` 重置。")

    async def _dispatch(self, dm_room_id: str, user_id: str, text: str) -> None:
        lower = text.lower().strip()

        if lower in ("/help", "help", "帮助"):
            await self._send_bot_message(dm_room_id, HELP_TEXT)
            return

        if lower == "/cancel":
            cancelled = await self.store.cancel_active_session(user_id)
            msg = "✅ 已取消当前草稿。" if cancelled else "没有进行中的草稿。"
            await self._send_bot_message(dm_room_id, msg)
            return

        if lower == "/send":
            await self._handle_send(dm_room_id, user_id)
            return

        if lower == "/save":
            await self._handle_save(dm_room_id, user_id)
            return

        if lower == "/retry":
            await self._handle_retry(dm_room_id, user_id)
            return

        m = re.match(r"^/draft\s+(\S+)\s+(.+)$", text, re.IGNORECASE | re.DOTALL)
        if m:
            target_room, topic = m.group(1), m.group(2).strip()
            await self._handle_draft(dm_room_id, user_id, target_room, topic)
            return

        m = re.match(r"^/digest\s+(\S+)\s+(.+)$", text, re.IGNORECASE | re.DOTALL)
        if m:
            target_room, time_range = m.group(1), m.group(2).strip()
            await self._handle_digest(dm_room_id, user_id, target_room, time_range)
            return

        # Non-command text → treat as refinement instruction for active session
        session = await self.store.get_active_session(user_id)
        if session and not session.is_expired:
            await self._handle_refinement(dm_room_id, user_id, session, text)
        else:
            await self._send_bot_message(
                dm_room_id,
                "没有进行中的草稿。发 `/draft <频道> <主题>` 开始起草，或 `/help` 查看命令。",
            )

    # ── Command handlers ──────────────────────────────────────────────────────

    async def _handle_draft(
        self, dm_room_id: str, user_id: str, target_room: str, topic: str
    ) -> None:
        await self.store.cancel_active_session(user_id)
        session = await self.store.create_session(user_id, target_room, command_type="draft")

        await self._send_bot_message(dm_room_id, f"⏳ 正在读取 {target_room} 并生成草稿…")

        prompt = self._build_draft_prompt(target_room, topic)
        answer, opencode_sid = await self.runner.run(prompt)

        if not answer:
            await self._send_bot_message(dm_room_id, "❌ Agent 未返回内容，请重试或检查 opencode 配置。")
            await self.store.cancel_active_session(user_id)
            return

        session.draft_text = answer
        session.opencode_session_id = opencode_sid
        session.conversation_history.append({"role": "user", "content": f"/draft {target_room} {topic}"})
        session.conversation_history.append({"role": "assistant", "content": answer})
        await self.store.update_session(session)

        reply = self._format_draft_reply(answer, version=1)
        await self._send_bot_message(dm_room_id, reply)

    async def _handle_digest(
        self, dm_room_id: str, user_id: str, target_room: str, time_range: str
    ) -> None:
        await self.store.cancel_active_session(user_id)
        session = await self.store.create_session(user_id, target_room, command_type="digest")

        await self._send_bot_message(dm_room_id, f"⏳ 正在分析 {target_room} {time_range} 的内容…")

        prompt = self._build_digest_prompt(target_room, time_range)
        answer, opencode_sid = await self.runner.run(prompt)

        if not answer:
            await self._send_bot_message(dm_room_id, "❌ Agent 未返回内容，请重试。")
            await self.store.cancel_active_session(user_id)
            return

        session.draft_text = answer
        session.opencode_session_id = opencode_sid
        session.conversation_history.append({"role": "user", "content": f"/digest {target_room} {time_range}"})
        session.conversation_history.append({"role": "assistant", "content": answer})
        await self.store.update_session(session)

        reply = self._format_digest_reply(answer)
        await self._send_bot_message(dm_room_id, reply)

    async def _handle_refinement(
        self, dm_room_id: str, user_id: str, session: DraftSession, instruction: str
    ) -> None:
        await self._send_bot_message(dm_room_id, "⏳ 正在修改草稿…")

        version = len([m for m in session.conversation_history if m["role"] == "assistant"]) + 1
        prompt = f"用户的修改要求：{instruction}\n\n请按要求修改上一版草稿，输出完整新版本。"
        answer, _ = await self.runner.run(prompt, session_id=session.opencode_session_id or None)

        if not answer:
            await self._send_bot_message(dm_room_id, "❌ 修改失败，请重试。")
            return

        session.draft_text = answer
        session.conversation_history.append({"role": "user", "content": instruction})
        session.conversation_history.append({"role": "assistant", "content": answer})
        await self.store.update_session(session)

        reply = self._format_draft_reply(answer, version=version)
        await self._send_bot_message(dm_room_id, reply)

    async def _handle_retry(self, dm_room_id: str, user_id: str) -> None:
        session = await self.store.get_active_session(user_id)
        if not session or session.is_expired:
            await self._send_bot_message(dm_room_id, "没有进行中的草稿可以重新生成。")
            return

        await self._send_bot_message(dm_room_id, "⏳ 重新生成中…")
        prompt = "请重新生成一版草稿，可以调整表达方式，保持同样的核心内容。"
        answer, _ = await self.runner.run(prompt, session_id=session.opencode_session_id or None)

        if not answer:
            await self._send_bot_message(dm_room_id, "❌ 重新生成失败，请重试。")
            return

        version = len([m for m in session.conversation_history if m["role"] == "assistant"]) + 1
        session.draft_text = answer
        session.conversation_history.append({"role": "user", "content": "/retry"})
        session.conversation_history.append({"role": "assistant", "content": answer})
        await self.store.update_session(session)

        reply = self._format_draft_reply(answer, version=version)
        await self._send_bot_message(dm_room_id, reply)

    async def _handle_send(self, dm_room_id: str, user_id: str) -> None:
        session = await self.store.get_active_session(user_id)
        if not session or session.is_expired:
            await self._send_bot_message(dm_room_id, "没有进行中的草稿可以发送。")
            return
        if not session.draft_text.strip():
            await self._send_bot_message(dm_room_id, "草稿为空，无法发送。")
            return

        target_room_id = await self._resolve_room_id(session.target_room_id)
        if not target_room_id:
            await self._send_bot_message(
                dm_room_id,
                f"❌ 找不到频道 `{session.target_room_id}`，请确认房间名称或 ID。",
            )
            return

        resp = await self._send_as_user(target_room_id, session.draft_text)
        if isinstance(resp, nio.RoomSendError):
            await self._send_bot_message(dm_room_id, f"❌ 发送失败：{resp.message}")
            return

        event_id = resp.event_id if hasattr(resp, "event_id") else ""
        session.status = SessionStatus.SENT
        await self.store.update_session(session)
        await self.store.record_sent(session, session.draft_text, event_id)
        await self._send_bot_message(dm_room_id, f"✅ 已以你的身份发到 {session.target_room_id}")

    async def _handle_save(self, dm_room_id: str, user_id: str) -> None:
        session = await self.store.get_active_session(user_id)
        if not session or session.is_expired:
            await self._send_bot_message(dm_room_id, "没有进行中的草稿可以保存。")
            return
        if session.command_type != "digest":
            await self._send_bot_message(
                dm_room_id,
                "只有 `/digest` 生成的纪要才能用 `/save` 保存到 vault。"
                "回复消息请用 `/send`。",
            )
            return

        await self._send_bot_message(dm_room_id, "⏳ 正在保存到 vault…")
        save_prompt = (
            "请将上面的纪要草稿以标准格式保存到 vault。"
            "使用 /obsidian-save 命令，遵循 AI-first 规范，"
            f"目标路径：Knowledge/ 目录，文件名基于日期和主题。"
        )
        answer, _ = await self.runner.run(save_prompt, session_id=session.opencode_session_id or None)

        session.status = SessionStatus.SAVED
        await self.store.update_session(session)
        await self._send_bot_message(dm_room_id, f"✅ 已保存到 vault。\n\n{answer[:200] if answer else ''}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_draft_prompt(self, target_room: str, topic: str) -> str:
        return (
            f"{DRAFT_SYSTEM_PROMPT}\n\n"
            f"目标频道：{target_room}\n"
            f"用户指令：{topic}\n\n"
            f"请用 list_rooms 和 get_recent_messages MCP 工具读取 {target_room} 的近期消息，"
            f"同时用你的 Read 和 Grep 工具搜索相关 vault 笔记，然后起草回复。"
        )

    def _build_digest_prompt(self, target_room: str, time_range: str) -> str:
        return (
            f"{DIGEST_SYSTEM_PROMPT}\n\n"
            f"目标频道：{target_room}，时间范围：{time_range}\n\n"
            f"请用 get_recent_messages MCP 工具读取 {target_room} 的近期消息，"
            f"然后生成符合 vault AI-first 规范的纪要草稿（包含 frontmatter、preamble、wikilinks）。"
        )

    @staticmethod
    def _format_draft_reply(draft: str, version: int) -> str:
        return (
            f"─── 草稿 v{version} ───\n"
            f"{draft}\n"
            f"────────────\n"
            f"`/send` 发送 · `/retry` 重新生成 · `/cancel` 取消 · 或直接说怎么改"
        )

    @staticmethod
    def _format_digest_reply(draft: str) -> str:
        return (
            f"─── 纪要草稿 ───\n"
            f"{draft}\n"
            f"────────────\n"
            f"`/save` 保存到 vault · `/retry` 重新生成 · `/cancel` 取消 · 或直接说怎么改"
        )

    async def _send_bot_message(self, room_id: str, text: str) -> None:
        if not self._bot_client:
            return
        await self._bot_client.room_send(
            room_id,
            message_type="m.room.message",
            content={"msgtype": "m.text", "body": text,
                     "format": "org.matrix.custom.html",
                     "formatted_body": _markdown_to_html(text)},
        )

    async def _send_as_user(self, room_id: str, text: str):
        if not self._user_client:
            raise RuntimeError("User client not initialized")
        return await self._user_client.room_send(
            room_id,
            message_type="m.room.message",
            content={"msgtype": "m.text", "body": text},
        )

    async def _resolve_room_id(self, room_ref: str) -> str | None:
        """Resolve '#room-name' or '!roomid:server' via the user's synced rooms."""
        if not self._user_client:
            return None
        await self._user_client.sync(timeout=5000, full_state=True)
        client = self._user_client
        if room_ref in client.rooms:
            return room_ref
        for rid, room in client.rooms.items():
            if room.display_name == room_ref or room.display_name == room_ref.lstrip("#"):
                return rid
        return None


def _markdown_to_html(text: str) -> str:
    """Minimal markdown → HTML for Matrix formatted messages."""
    import html as html_mod
    lines = text.split("\n")
    out = []
    for line in lines:
        escaped = html_mod.escape(line)
        # Bold
        escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
        # Inline code
        escaped = re.sub(r"`(.+?)`", r"<code>\1</code>", escaped)
        out.append(escaped)
    return "<br/>".join(out)

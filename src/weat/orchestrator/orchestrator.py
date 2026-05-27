"""
Orchestrator — monitors the WeAt command room and drives the draft workflow.

State machine per session:
  idle ──[/draft or /digest]──► active (generating draft)
  active ──[refinement text]──► active (refining)
  active ──[/retry]──────────► active (regenerating)
  active ──[/send]────────────► sent   (message delivered to target room)
  active ──[/save]────────────► saved  (note written to vault)
  active ──[/cancel]──────────► cancelled

Single Matrix account: the same credentials both listen for commands and send
to target rooms. Draft replies are sent into the WeAt command room and filtered
out from processing via event ID tracking.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from typing import Awaitable, Callable

import nio

from ..config.settings import Config
from .opencode_runner import OpenCodeRunner
from .session_store import DraftSession, SessionStatus, SessionStore

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
        self._client: nio.AsyncClient | None = None
        self._running = False
        self._startup_ts: int = 0
        self._sent_event_ids: set[str] = set()

    async def start(self) -> None:
        await self.store.init()

        proxy = (
            os.environ.get("HTTPS_PROXY")
            or os.environ.get("https_proxy")
            or os.environ.get("ALL_PROXY")
            or os.environ.get("all_proxy")
        )
        self._client = nio.AsyncClient(
            self.config.homeserver, self.config.user_id, proxy=proxy
        )
        self._client.access_token = self.config.access_token
        self._client.user_id = self.config.user_id

        self.runner.write_opencode_config(
            homeserver=self.config.homeserver,
            user_id=self.config.user_id,
            access_token=self.config.access_token,
        )

        self._client.add_event_callback(self._on_message, nio.RoomMessageText)
        self._running = True
        self._startup_ts = int(time.time() * 1000)

        logger.info("Starting sync loop (weat_room=%s) ...", self.config.weat_room_id)
        first_sync = True
        while self._running:
            resp = await self._client.sync(
                timeout=30000,
                full_state=first_sync,
                since=self._client.next_batch if not first_sync else None,
            )
            first_sync = False
            if isinstance(resp, nio.SyncError):
                logger.error("Sync error: %s", resp.message)
                await asyncio.sleep(5)
                continue
            expired = await self.store.expire_stale_sessions(self.config.session_timeout_minutes)
            if expired:
                logger.info("Expired %d stale sessions", expired)

    async def stop(self) -> None:
        self._running = False
        if self._client:
            await self._client.close()
        await self.store.close()

    async def _on_message(self, room: nio.MatrixRoom, event: nio.RoomMessageText) -> None:
        # Only handle the WeAt command room
        if room.room_id != self.config.weat_room_id:
            return
        # Skip messages that existed before the bridge started
        if event.server_timestamp <= self._startup_ts:
            return
        # Skip messages sent by the bridge itself
        if event.event_id in self._sent_event_ids:
            return

        text = event.body.strip()
        user_id = event.sender

        try:
            await self._dispatch(user_id, text)
        except Exception:
            logger.exception("Error handling message from %s", user_id)
            await self._send("❌ 出错了，请稍后再试或发 `/cancel` 重置。")

    async def _dispatch(self, user_id: str, text: str) -> None:
        lower = text.lower().strip()

        if lower in ("/help", "help", "帮助"):
            await self._send(HELP_TEXT)
            return

        if lower == "/cancel":
            cancelled = await self.store.cancel_active_session(user_id)
            await self._send("✅ 已取消当前草稿。" if cancelled else "没有进行中的草稿。")
            return

        if lower == "/send":
            await self._handle_send(user_id)
            return

        if lower == "/save":
            await self._handle_save(user_id)
            return

        if lower == "/retry":
            await self._handle_retry(user_id)
            return

        m = re.match(r"^/draft\s+(\S+)\s+(.+)$", text, re.IGNORECASE | re.DOTALL)
        if m:
            await self._handle_draft(user_id, m.group(1), m.group(2).strip())
            return

        m = re.match(r"^/digest\s+(\S+)\s+(.+)$", text, re.IGNORECASE | re.DOTALL)
        if m:
            await self._handle_digest(user_id, m.group(1), m.group(2).strip())
            return

        # Non-command → refinement instruction for active session
        session = await self.store.get_active_session(user_id)
        if session and not session.is_expired:
            await self._handle_refinement(user_id, session, text)
        else:
            await self._send("没有进行中的草稿。发 `/draft <频道> <主题>` 开始起草，或 `/help` 查看命令。")

    # ── Command handlers ──────────────────────────────────────────────────────

    async def _handle_draft(self, user_id: str, target_room: str, topic: str) -> None:
        await self.store.cancel_active_session(user_id)
        session = await self.store.create_session(user_id, target_room, command_type="draft")

        await self._send(f"⏳ 正在读取 {target_room} 并生成草稿…")

        prompt = self._build_draft_prompt(target_room, topic)
        answer, opencode_sid = await self.runner.run(prompt)

        if not answer:
            await self._send("❌ Agent 未返回内容，请重试或检查 opencode 配置。")
            await self.store.cancel_active_session(user_id)
            return

        session.draft_text = answer
        session.opencode_session_id = opencode_sid
        session.conversation_history.append({"role": "user", "content": f"/draft {target_room} {topic}"})
        session.conversation_history.append({"role": "assistant", "content": answer})
        await self.store.update_session(session)

        await self._send(self._format_draft_reply(answer, version=1))

    async def _handle_digest(self, user_id: str, target_room: str, time_range: str) -> None:
        await self.store.cancel_active_session(user_id)
        session = await self.store.create_session(user_id, target_room, command_type="digest")

        await self._send(f"⏳ 正在分析 {target_room} {time_range} 的内容…")

        prompt = self._build_digest_prompt(target_room, time_range)
        answer, opencode_sid = await self.runner.run(prompt)

        if not answer:
            await self._send("❌ Agent 未返回内容，请重试。")
            await self.store.cancel_active_session(user_id)
            return

        session.draft_text = answer
        session.opencode_session_id = opencode_sid
        session.conversation_history.append({"role": "user", "content": f"/digest {target_room} {time_range}"})
        session.conversation_history.append({"role": "assistant", "content": answer})
        await self.store.update_session(session)

        await self._send(self._format_digest_reply(answer))

    async def _handle_refinement(self, user_id: str, session: DraftSession, instruction: str) -> None:
        await self._send("⏳ 正在修改草稿…")

        version = len([m for m in session.conversation_history if m["role"] == "assistant"]) + 1
        prompt = f"用户的修改要求：{instruction}\n\n请按要求修改上一版草稿，输出完整新版本。"
        answer, _ = await self.runner.run(prompt, session_id=session.opencode_session_id or None)

        if not answer:
            await self._send("❌ 修改失败，请重试。")
            return

        session.draft_text = answer
        session.conversation_history.append({"role": "user", "content": instruction})
        session.conversation_history.append({"role": "assistant", "content": answer})
        await self.store.update_session(session)

        await self._send(self._format_draft_reply(answer, version=version))

    async def _handle_retry(self, user_id: str) -> None:
        session = await self.store.get_active_session(user_id)
        if not session or session.is_expired:
            await self._send("没有进行中的草稿可以重新生成。")
            return

        await self._send("⏳ 重新生成中…")
        prompt = "请重新生成一版草稿，可以调整表达方式，保持同样的核心内容。"
        answer, _ = await self.runner.run(prompt, session_id=session.opencode_session_id or None)

        if not answer:
            await self._send("❌ 重新生成失败，请重试。")
            return

        version = len([m for m in session.conversation_history if m["role"] == "assistant"]) + 1
        session.draft_text = answer
        session.conversation_history.append({"role": "user", "content": "/retry"})
        session.conversation_history.append({"role": "assistant", "content": answer})
        await self.store.update_session(session)

        await self._send(self._format_draft_reply(answer, version=version))

    async def _handle_send(self, user_id: str) -> None:
        session = await self.store.get_active_session(user_id)
        if not session or session.is_expired:
            await self._send("没有进行中的草稿可以发送。")
            return
        if not session.draft_text.strip():
            await self._send("草稿为空，无法发送。")
            return

        target_room_id = await self._resolve_room_id(session.target_room_id)
        if not target_room_id:
            await self._send(f"❌ 找不到频道 `{session.target_room_id}`，请确认房间名称或 ID。")
            return

        resp = await self._client.room_send(
            target_room_id,
            message_type="m.room.message",
            content={"msgtype": "m.text", "body": session.draft_text},
        )
        if isinstance(resp, nio.RoomSendError):
            await self._send(f"❌ 发送失败：{resp.message}")
            return

        event_id = resp.event_id if hasattr(resp, "event_id") else ""
        session.status = SessionStatus.SENT
        await self.store.update_session(session)
        await self.store.record_sent(session, session.draft_text, event_id)
        await self._send(f"✅ 已发到 {session.target_room_id}")

    async def _handle_save(self, user_id: str) -> None:
        session = await self.store.get_active_session(user_id)
        if not session or session.is_expired:
            await self._send("没有进行中的草稿可以保存。")
            return
        if session.command_type != "digest":
            await self._send("只有 `/digest` 生成的纪要才能用 `/save` 保存到 vault。回复消息请用 `/send`。")
            return

        await self._send("⏳ 正在保存到 vault…")
        save_prompt = (
            "请将上面的纪要草稿以标准格式保存到 vault。"
            "使用 /obsidian-save 命令，遵循 AI-first 规范，"
            "目标路径：Knowledge/ 目录，文件名基于日期和主题。"
        )
        answer, _ = await self.runner.run(save_prompt, session_id=session.opencode_session_id or None)

        session.status = SessionStatus.SAVED
        await self.store.update_session(session)
        await self._send(f"✅ 已保存到 vault。\n\n{answer[:200] if answer else ''}")

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

    async def _send(self, text: str) -> None:
        if not self._client:
            return
        resp = await self._client.room_send(
            self.config.weat_room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": text,
                "format": "org.matrix.custom.html",
                "formatted_body": _markdown_to_html(text),
            },
        )
        if hasattr(resp, "event_id") and resp.event_id:
            self._sent_event_ids.add(resp.event_id)
            if len(self._sent_event_ids) > 2000:
                self._sent_event_ids = set(list(self._sent_event_ids)[-1000:])

    async def _resolve_room_id(self, room_ref: str) -> str | None:
        if not self._client:
            return None
        await self._client.sync(timeout=5000, full_state=True)
        if room_ref in self._client.rooms:
            return room_ref
        for rid, room in self._client.rooms.items():
            if room.display_name == room_ref or room.display_name == room_ref.lstrip("#"):
                return rid
        return None


def _markdown_to_html(text: str) -> str:
    import html as html_mod
    lines = text.split("\n")
    out = []
    for line in lines:
        escaped = html_mod.escape(line)
        escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
        escaped = re.sub(r"`(.+?)`", r"<code>\1</code>", escaped)
        out.append(escaped)
    return "<br/>".join(out)

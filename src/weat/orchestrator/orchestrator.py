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
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

import aiohttp
import nio

from ..config.settings import Config
from .opencode_runner import OpenCodeRunner
from .session_store import DraftSession, SessionStatus, SessionStore

logger = logging.getLogger(__name__)

_BOT_MARKER = "dev.weat.bot"

HELP_TEXT = """\
**WeAt AI 副驾驶** — 命令列表：

📝 **起草回复**
`/weat-draft <频道> <主题>`  — 起草一条回复（如 `/weat-draft #开发组 解释上周的 P1`）

📋 **总结群聊**
`/weat-digest <频道> <时间范围>` — 生成纪要草稿（如 `/weat-digest #开发组 本周`）

✅ **操作草稿**
`/weat-send`   — 以你的身份发到目标频道
`/weat-save`   — 保存为 Obsidian 笔记
`/weat-retry`  — 重新生成当前草稿
`/weat-cancel` — 放弃当前草稿
`/weat-help`   — 显示此帮助

💬 **直接说要怎么改** — 非命令消息默认为对当前草稿的改稿指令。
"""

_TOOL_BUDGET_RULES = """\
⚠️ 工具调用纪律（最重要）：
- 总共最多调用 8 次工具，超过即必须停止调研。
- 每次调用前先问自己：信息是否已足够回答？如足够，立刻停止调用，直接输出文字回答。
- 禁止"为了周全再读一份"。宁可基于不完整信息给出最佳猜测，也不要继续无止境地读文件。
- 你的最终产出必须是一段文字回答，而不是一连串工具调用。没有文字回答 = 任务失败。
"""

DRAFT_SYSTEM_PROMPT = f"""\
你是用户的私人 AI 副驾驶，帮助起草 Matrix 群聊回复。

任务：根据群聊历史和用户的个人知识库（vault），起草一条清晰、自然的回复。

{_TOOL_BUDGET_RULES}

输出格式：
1. 直接给出草稿正文（不要加"草稿："前缀）
2. 在草稿后空一行，列出引用来源（格式：📚 引用：[[笔记名]] / 群聊 发言人 时间）
3. 在引用后空一行，用一句话描述你的步骤（格式：🤖 步骤：...）

语气：和用户平时发言风格一致，自然、专业，不要过于正式。
"""

DIGEST_SYSTEM_PROMPT = f"""\
你是用户的私人 AI 副驾驶，帮助整理群聊纪要。

任务：根据指定时间段的群聊内容，生成结构化的纪要草稿，供用户保存到 Obsidian 知识库。

{_TOOL_BUDGET_RULES}

输出格式：
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
            provider=config.opencode_provider,
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
        # Only accept commands from the configured owner account
        if event.sender != self.config.user_id:
            logger.debug("ignoring message from non-owner %s", event.sender)
            return
        # Skip messages that existed before the bridge started
        if event.server_timestamp <= self._startup_ts:
            logger.debug("ignoring pre-startup message (ts=%d)", event.server_timestamp)
            return
        # Skip messages sent by the bridge itself (custom marker — survives restarts)
        if event.source.get("content", {}).get(_BOT_MARKER):
            logger.debug("ignoring bot echo (marker)")
            return
        # Fallback: skip by event_id (same-session race condition guard)
        if event.event_id in self._sent_event_ids:
            logger.debug("ignoring bot echo (event_id)")
            return

        text = event.body.strip()
        user_id = event.sender
        logger.info("← [%s] %s", user_id, text[:120])

        try:
            await self._dispatch(user_id, text)
        except Exception:
            logger.exception("Error handling message from %s", user_id)
            await self._send("❌ 出错了，请稍后再试或发 `/weat-cancel` 重置。")

    async def _dispatch(self, user_id: str, text: str) -> None:
        lower = text.lower().strip()

        if lower == "/weat-help":
            await self._send(HELP_TEXT)
            return

        if lower == "/weat-cancel":
            cancelled = await self.store.cancel_active_session(user_id)
            await self._send("✅ 已取消当前草稿。" if cancelled else "没有进行中的草稿。")
            return

        if lower == "/weat-send":
            await self._handle_send(user_id)
            return

        if lower == "/weat-save":
            await self._handle_save(user_id)
            return

        if lower == "/weat-retry":
            await self._handle_retry(user_id)
            return

        m = re.match(r"^/weat-draft\s+(\S+)\s+(.+)$", text, re.IGNORECASE | re.DOTALL)
        if m:
            await self._handle_draft(user_id, m.group(1), m.group(2).strip())
            return

        m = re.match(r"^/weat-digest\s+(\S+)\s+(.+)$", text, re.IGNORECASE | re.DOTALL)
        if m:
            await self._handle_digest(user_id, m.group(1), m.group(2).strip())
            return

        # Non-command → refinement instruction for active session
        session = await self.store.get_active_session(user_id)
        if session and not session.is_expired:
            await self._handle_refinement(user_id, session, text)
        else:
            await self._send("没有进行中的草稿。发 `/weat-draft <频道> <主题>` 开始起草，或 `/weat-help` 查看命令。")

    # ── Command handlers ──────────────────────────────────────────────────────

    async def _handle_draft(self, user_id: str, target_room: str, topic: str) -> None:
        await self.store.cancel_active_session(user_id)
        session = await self.store.create_session(user_id, target_room, command_type="draft")

        await self._send(f"⏳ 正在读取 {target_room} 并生成草稿…")

        prompt = await self._build_draft_prompt(target_room, topic)
        answer, opencode_sid = await self.runner.run(prompt)

        if not answer:
            await self._send("❌ Agent 未返回内容，请重试或检查 opencode 配置。")
            await self.store.cancel_active_session(user_id)
            return

        session.draft_text = answer
        session.opencode_session_id = opencode_sid
        session.conversation_history.append({"role": "user", "content": f"/weat-draft {target_room} {topic}"})
        session.conversation_history.append({"role": "assistant", "content": answer})
        await self.store.update_session(session)

        await self._send(self._format_draft_reply(answer, version=1))

    async def _handle_digest(self, user_id: str, target_room: str, time_range: str) -> None:
        await self.store.cancel_active_session(user_id)
        session = await self.store.create_session(user_id, target_room, command_type="digest")

        await self._send(f"⏳ 正在分析 {target_room} {time_range} 的内容…")

        prompt = await self._build_digest_prompt(target_room, time_range)
        answer, opencode_sid = await self.runner.run(prompt)

        if not answer:
            await self._send("❌ Agent 未返回内容，请重试。")
            await self.store.cancel_active_session(user_id)
            return

        session.draft_text = answer
        session.opencode_session_id = opencode_sid
        session.conversation_history.append({"role": "user", "content": f"/weat-digest {target_room} {time_range}"})
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
        session.conversation_history.append({"role": "user", "content": "/weat-retry"})
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

        # Mark SENT in DB before sending to prevent double-send if room_send succeeds
        # but a later DB write fails. If room_send fails after this, user must re-draft.
        session.status = SessionStatus.SENT
        await self.store.update_session(session)

        resp = await self._client.room_send(
            target_room_id,
            message_type="m.room.message",
            content={"msgtype": "m.text", "body": session.draft_text},
        )
        if isinstance(resp, nio.RoomSendError):
            await self._send(f"❌ 发送失败：{resp.message}")
            return

        event_id = resp.event_id if hasattr(resp, "event_id") else ""
        await self.store.record_sent(session, session.draft_text, event_id)
        await self._send(f"✅ 已发到 {session.target_room_id}")

    async def _handle_save(self, user_id: str) -> None:
        session = await self.store.get_active_session(user_id)
        if not session or session.is_expired:
            await self._send("没有进行中的草稿可以保存。")
            return
        if session.command_type != "digest":
            await self._send("只有 `/weat-digest` 生成的纪要才能用 `/weat-save` 保存到 vault。回复消息请用 `/weat-send`。")
            return

        await self._send("⏳ 正在保存到 vault…")
        save_prompt = (
            "请将上面的纪要草稿以标准格式保存到 vault。"
            "使用 /obsidian-save 命令，遵循 AI-first 规范，"
            "目标路径：Knowledge/ 目录，文件名基于日期和主题。"
        )
        answer, _ = await self.runner.run(save_prompt, session_id=session.opencode_session_id or None)

        if not answer:
            await self._send("❌ 保存失败，agent 未返回内容，请重试。")
            return

        session.status = SessionStatus.SAVED
        await self.store.update_session(session)
        await self._send(f"✅ 已保存到 vault。\n\n{answer[:200]}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _fetch_recent_messages(self, room_id: str, limit: int = 30) -> list[dict]:
        """Fetch recent text messages via Matrix REST (bypasses agent tool calls)."""
        headers = {"Authorization": f"Bearer {self.config.access_token}"}
        url = f"{self.config.homeserver}/_matrix/client/v3/rooms/{room_id}/messages"
        try:
            async with aiohttp.ClientSession(headers=headers, trust_env=True) as s:
                async with s.get(
                    url,
                    params={"limit": limit, "dir": "b"},
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as r:
                    if r.status != 200:
                        logger.warning("fetch messages failed (%d): %s", r.status, await r.text())
                        return []
                    data = await r.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.warning("fetch messages error: %s", e)
            return []
        msgs = []
        for e in reversed(data.get("chunk", [])):
            if e.get("type") != "m.room.message":
                continue
            if e.get("content", {}).get("msgtype") != "m.text":
                continue
            ts = e.get("origin_server_ts", 0)
            dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%m-%d %H:%M")
            msgs.append({
                "sender": e.get("sender", ""),
                "time": dt,
                "body": e.get("content", {}).get("body", ""),
            })
        return msgs

    def _search_vault(self, query: str, limit: int = 5) -> list[tuple[Path, str]]:
        """Find vault .md notes matching keywords in `query`. Returns [(path, snippet)]."""
        vault = Path(self.config.vault_path)
        if not vault.is_dir():
            return []
        q = query.lower()
        keywords = [w for w in re.split(r"\s+", q) if len(w) >= 2]
        if not keywords:
            keywords = [q] if q else []
        if not keywords:
            return []

        scored: list[tuple[int, Path, str]] = []
        for md in vault.rglob("*.md"):
            try:
                if md.stat().st_size > 200_000:
                    continue
                content = md.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            lower = content.lower()
            score = sum(lower.count(kw) for kw in keywords)
            if score == 0:
                continue
            snippet = ""
            for kw in keywords:
                idx = lower.find(kw)
                if idx >= 0:
                    start = max(0, idx - 100)
                    end = min(len(content), idx + 400)
                    snippet = content[start:end].strip()
                    break
            scored.append((score, md, snippet))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [(p, s) for _, p, s in scored[:limit]]

    @staticmethod
    def _format_msg_block(msgs: list[dict]) -> str:
        if not msgs:
            return "（暂无近期消息）"
        return "\n".join(f"[{m['time']}] {m['sender']}: {m['body']}" for m in msgs)

    def _format_vault_block(self, notes: list[tuple[Path, str]]) -> str:
        if not notes:
            return "（vault 中未找到相关笔记）"
        vault = Path(self.config.vault_path)
        out = []
        for path, snippet in notes:
            try:
                rel = path.relative_to(vault)
            except ValueError:
                rel = path
            out.append(f"📄 [[{rel}]]\n{snippet}")
        return "\n\n".join(out)

    async def _build_draft_prompt(self, target_room: str, topic: str) -> str:
        room_id = await self._resolve_room_id(target_room)
        msg_block = "（未能解析目标房间，可用 list_rooms / get_recent_messages 工具补充）"
        if room_id:
            msgs = await self._fetch_recent_messages(room_id, limit=30)
            msg_block = self._format_msg_block(msgs)
            logger.info("pre-fetched %d messages from %s", len(msgs), room_id)

        notes = self._search_vault(topic, limit=5)
        vault_block = self._format_vault_block(notes)
        logger.info("pre-fetched %d vault notes for topic", len(notes))

        return (
            f"{DRAFT_SYSTEM_PROMPT}\n\n"
            f"目标频道：{target_room}（room_id={room_id or '未知'}）\n"
            f"用户指令：{topic}\n\n"
            f"以下材料已为你预先准备好，请直接基于此起草，不要再调工具重复获取这些信息。\n"
            f"信息不足时才需要补充工具调用（vault 用 Read/Grep/Glob，群聊用 MCP 工具）。\n\n"
            f"=== 该频道近期消息（按时间正序，最多 30 条） ===\n"
            f"{msg_block}\n\n"
            f"=== Vault 中可能相关的笔记 ===\n"
            f"{vault_block}\n"
        )

    async def _build_digest_prompt(self, target_room: str, time_range: str) -> str:
        room_id = await self._resolve_room_id(target_room)
        msg_block = "（未能解析目标房间，可用 list_rooms / get_recent_messages 工具补充）"
        if room_id:
            msgs = await self._fetch_recent_messages(room_id, limit=200)
            msg_block = self._format_msg_block(msgs)
            logger.info("pre-fetched %d messages from %s for digest", len(msgs), room_id)

        return (
            f"{DIGEST_SYSTEM_PROMPT}\n\n"
            f"目标频道：{target_room}（room_id={room_id or '未知'}），时间范围：{time_range}\n\n"
            f"以下是该频道最近的消息（按时间正序，最多 200 条），请筛选落在「{time_range}」内的内容并整理成纪要。\n"
            f"不要再调 list_rooms / get_recent_messages，信息已经在这里。\n\n"
            f"=== 频道消息 ===\n"
            f"{msg_block}\n"
        )

    @staticmethod
    def _format_draft_reply(draft: str, version: int) -> str:
        return (
            f"─── 草稿 v{version} ───\n"
            f"{draft}\n"
            f"────────────\n"
            f"`/weat-send` 发送 · `/weat-retry` 重新生成 · `/weat-cancel` 取消 · 或直接说怎么改"
        )

    @staticmethod
    def _format_digest_reply(draft: str) -> str:
        return (
            f"─── 纪要草稿 ───\n"
            f"{draft}\n"
            f"────────────\n"
            f"`/weat-save` 保存到 vault · `/weat-retry` 重新生成 · `/weat-cancel` 取消 · 或直接说怎么改"
        )

    async def _send(self, text: str) -> None:
        if not self._client:
            return
        logger.info("→ [bot] %s", text[:120].replace("\n", "↵"))
        resp = await self._client.room_send(
            self.config.weat_room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": text,
                "format": "org.matrix.custom.html",
                "formatted_body": _markdown_to_html(text),
                _BOT_MARKER: True,
            },
        )
        if hasattr(resp, "event_id") and resp.event_id:
            self._sent_event_ids.add(resp.event_id)
            if len(self._sent_event_ids) > 2000:
                self._sent_event_ids = set(list(self._sent_event_ids)[-1000:])

    async def _resolve_room_id(self, room_ref: str) -> str | None:
        if not self._client:
            return None
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

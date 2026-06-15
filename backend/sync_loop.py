"""
Matrix sync 循环 — 每用户独立后台任务

工作方式：
1. 用户建立 WebSocket 连接时，启动一个后台 sync 任务
2. 循环调用 Tuwunel /sync（long polling）
3. 有事件时通过 WebSocket 推送给前端
4. 用户断开连接时取消 sync 任务
"""

import asyncio
import json
import logging
from typing import Any

from backend import matrix_api

logger = logging.getLogger(__name__)


class SyncManager:
    """管理所有在线用户的 sync 循环。"""

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}
        self._connections: dict[str, set] = {}  # user_id → set of websocket send queues

    def register_ws(self, user_id: str, send_queue: asyncio.Queue) -> None:
        """注册一个 WebSocket 连接的发送队列。"""
        self._connections.setdefault(user_id, set()).add(send_queue)
        if user_id not in self._tasks:
            self._tasks[user_id] = asyncio.create_task(
                self._sync_loop(user_id, send_queue),
                name=f"sync-{user_id}",
            )
            logger.info("Started sync loop for %s", user_id)

    def unregister_ws(self, user_id: str, send_queue: asyncio.Queue) -> None:
        """移除一个 WebSocket 连接的发送队列。"""
        conns = self._connections.get(user_id, set())
        conns.discard(send_queue)
        if not conns:
            task = self._tasks.pop(user_id, None)
            if task:
                task.cancel()
                logger.info("Stopped sync loop for %s (no WS connections)", user_id)

    async def send_to_user(self, user_id: str, event: dict) -> None:
        """向用户的所有连接广播事件。"""
        msg = json.dumps(event, ensure_ascii=False, default=str)
        for q in self._connections.get(user_id, set()):
            await q.put(msg)

    async def _sync_loop(self, user_id: str, token: str | None = None) -> None:
        """每个用户的 sync 后台循环。"""
        next_batch: str | None = None
        while True:
            try:
                data = await matrix_api.sync(token or "", since=next_batch, timeout=30000)
                if isinstance(data, bytes):
                    logger.warning("sync returned non-JSON for %s, retrying", user_id)
                    await asyncio.sleep(5)
                    continue

                next_batch = data.get("next_batch", next_batch)
                rooms = data.get("rooms", {}).get("join", {})

                for room_id, room_data in rooms.items():
                    # 处理时间线新事件
                    for event in room_data.get("timeline", {}).get("events", []):
                        if event.get("type") == "m.room.message":
                            await self.send_to_user(user_id, {
                                "type": "m.room.message",
                                "room_id": room_id,
                                "content": event.get("content", {}),
                                "sender": event.get("sender", ""),
                                "event_id": event.get("event_id", ""),
                                "origin_server_ts": event.get("origin_server_ts", 0),
                            })
                    # 处理 ephemeral 事件（正在输入等）
                    # 暂不处理

            except asyncio.CancelledError:
                logger.info("Sync loop cancelled for %s", user_id)
                return
            except Exception:
                logger.exception("Sync loop error for %s, retrying in 10s", user_id)
                await asyncio.sleep(10)


# 全局单例
sync_manager = SyncManager()

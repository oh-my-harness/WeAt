"""
Tuwunel (Matrix) REST API 封装

封装 Tuwunel 的 Matrix Client-Server API 调用。
所有方法返回 dict, 调用方处理异常。
"""

import asyncio
import json
import logging
import os
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

# 优先使用环境变量，默认 localhost（本地开发）
MATRIX_BASE = os.environ.get("MATRIX_BASE", "http://localhost:8008")


def _headers(token: str | None = None) -> dict:
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


async def _get(path: str, token: str | None = None, params: dict | None = None) -> dict[str, Any] | bytes:
    """GET 请求，返回 JSON dict；当服务器返回非 JSON 时返回 bytes。"""
    url = f"{MATRIX_BASE}{path}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=_headers(token), params=params) as resp:
            text = await resp.text()
            logger.debug("GET %s → %s %s", url, resp.status, text[:200])
            if resp.status >= 400:
                raise RuntimeError(f"Tuwunel API error {resp.status}: {text}")
            try:
                return await resp.json()
            except Exception:
                return text.encode()


async def _post(path: str, token: str | None = None, json: dict | None = None) -> dict[str, Any]:
    """POST 请求，返回 JSON。"""
    url = f"{MATRIX_BASE}{path}"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=_headers(token), json=json) as resp:
            text = await resp.text()
            logger.debug("POST %s → %s %s", url, resp.status, text[:200])
            if resp.status >= 400:
                raise RuntimeError(f"Tuwunel API error {resp.status}: {text}")
            try:
                return await resp.json()
            except Exception:
                return {"raw": text}


async def _put(path: str, token: str | None = None, json: dict | None = None) -> dict[str, Any]:
    url = f"{MATRIX_BASE}{path}"
    async with aiohttp.ClientSession() as session:
        async with session.put(url, headers=_headers(token), json=json) as resp:
            text = await resp.text()
            logger.debug("PUT %s → %s %s", url, resp.status, text[:200])
            if resp.status >= 400:
                raise RuntimeError(f"Tuwunel API error {resp.status}: {text}")
            try:
                return await resp.json()
            except Exception:
                return {"raw": text}


# ── Public API ──────────────────────────────────────────────────────────────


async def login(username: str, password: str) -> dict:
    """登录 Matrix，返回 {access_token, user_id, device_id}。"""
    body = {
        "type": "m.login.password",
        "identifier": {"type": "m.id.user", "user": username},
        "password": password,
        "initial_device_display_name": "WeAt Web",
    }
    return await _post("/_matrix/client/v3/login", json=body)


async def get_rooms(token: str) -> list[dict]:
    """获取已加入的房间列表。返回 [room, ...]。"""
    data = await _get("/_matrix/client/v3/joined_rooms", token)
    rooms = data.get("joined_rooms", [])

    async def _fetch_name(room_id: str) -> dict:
        try:
            name_data = await _get(f"/_matrix/client/v3/rooms/{room_id}/state/m.room.name", token)
            name = name_data.get("name", "") if isinstance(name_data, dict) else ""
        except Exception:
            # m.room.name is optional in Matrix; unnamed rooms (DMs, new rooms) return 404
            name = ""
        return {"room_id": room_id, "name": name}

    return list(await asyncio.gather(*[_fetch_name(r) for r in rooms]))


async def get_messages(room_id: str, token: str, limit: int = 50) -> list[dict]:
    """获取房间历史消息。返回 [message, ...]，只含 m.room.message 事件。"""
    params = {"dir": "b", "limit": str(limit)}
    data = await _get(f"/_matrix/client/v3/rooms/{room_id}/messages", token, params=params)
    if isinstance(data, bytes):
        return []
    return [e for e in data.get("chunk", []) if e.get("type") == "m.room.message"]


async def send_message(room_id: str, token: str, body: str) -> dict:
    """发送消息。返回 {event_id}。"""
    content = {
        "msgtype": "m.text",
        "body": body,
    }
    txn_id = f"weat-{int(__import__('time').time() * 1000)}"
    return await _put(
        f"/_matrix/client/v3/rooms/{room_id}/send/m.room.message/{txn_id}",
        token,
        json=content,
    )


async def sync(token: str, since: str | None = None, timeout: int = 30000) -> dict:
    """Matrix /sync 长轮询。返回 sync response。"""
    params: dict[str, str | int] = {"timeout": timeout}
    if since:
        params["since"] = since
    return await _get("/_matrix/client/v3/sync", token, params=params)


async def register_user(username: str, password: str) -> dict:
    """注册新用户（仅在 allow_registration=true 时可用）。"""
    body = {
        "username": username,
        "password": password,
        "auth": {"type": "m.login.dummy"},
    }
    return await _post("/_matrix/client/v3/register", json=body)


async def get_user_info(token: str) -> dict:
    """获取当前用户信息。"""
    return await _get("/_matrix/client/v3/account/whoami", token)


ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
MATRIX_ADMIN_TOKEN = os.environ.get("MATRIX_ADMIN_TOKEN", "") or ADMIN_TOKEN

# ── 本地用户记录 ─────────────────────────────────────────────────────

USERS_FILE = os.environ.get("USERS_FILE", "/app/backend/users.json")


def _load_users() -> list[dict]:
    try:
        with open(USERS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_users(users: list[dict]):
    d = os.path.dirname(USERS_FILE)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


def record_user(username: str):
    """记录新注册的用户到本地文件。"""
    users = _load_users()
    existing = {u.get("name", "") for u in users}
    domain = os.environ.get("MATRIX_DOMAIN") or os.environ.get("SERVER_NAME", "localhost")
    full_id = f"@{username}:{domain}"
    if full_id not in existing:
        users.append({"name": full_id, "deactivated": False})
        _save_users(users)


def remove_user_record(user_id: str):
    """标记用户为已停用。"""
    users = _load_users()
    for u in users:
        if u.get("name") == user_id:
            u["deactivated"] = True
    _save_users(users)


async def get_registered_users() -> list[dict]:
    """获取已注册用户列表（从本地记录读取）。"""
    return _load_users()


# ── Tuwunel Admin API（基于 room-based admin 机制） ──────────────────

MATRIX_ADMIN_USER = os.environ.get("MATRIX_ADMIN_USER", "")
MATRIX_ADMIN_PASSWORD = os.environ.get("MATRIX_ADMIN_PASSWORD", "")
_tuwunel_admin_token: str | None = None


async def _get_admin_token() -> str:
    """获取 Tuwunel admin token。用 MATRIX_ADMIN_USER/PASSWORD 登录。"""
    global _tuwunel_admin_token
    if _tuwunel_admin_token:
        return _tuwunel_admin_token
    if not MATRIX_ADMIN_USER or not MATRIX_ADMIN_PASSWORD:
        raise RuntimeError("请设置 MATRIX_ADMIN_USER 和 MATRIX_ADMIN_PASSWORD 环境变量")
    result = await login(MATRIX_ADMIN_USER, MATRIX_ADMIN_PASSWORD)
    _tuwunel_admin_token = result["access_token"]
    return _tuwunel_admin_token


async def deactivate_user(user_id: str) -> dict:
    """停用用户（通过 Tuwunel suspend API）。"""
    # 先标记本地记录
    remove_user_record(user_id)
    # 再调用 Tuwunel suspend API
    try:
        token = await _get_admin_token()
        localpart = user_id.split(":")[0]
        domain = user_id.split(":", 1)[1] if ":" in user_id else "localhost"
        return await _put(
            f"/_matrix/client/v1/admin/suspend/{localpart}:{domain}",
            token=token,
            json={"suspended": True},
        )
    except Exception as e:
        logger.warning("Tuwunel suspend API failed (local record updated anyway): %s", e)
        return {"ok": True, "note": "local only"}


async def reset_password(username: str, new_password: str) -> dict:
    """重置用户密码。使用 Tuwunel admin API。"""
    if not MATRIX_ADMIN_TOKEN:
        raise RuntimeError("未设置 MATRIX_ADMIN_TOKEN 环境变量")
    localpart = username.split(":")[0].replace("@", "")
    domain = os.environ.get("MATRIX_DOMAIN", "localhost")
    return await _put(
        f"/_synapse/admin/v1/reset_password/@{localpart}:{domain}",
        token=MATRIX_ADMIN_TOKEN,
        json={"new_password": new_password},
    )


async def create_room(token: str, name: str, public: bool = False) -> dict:
    """创建新房间。返回 {room_id}。"""
    import re
    # room_alias_name 只支持 [a-z0-9_-]，中文等字符需要转换
    alias = re.sub(r"[^a-zA-Z0-9_-]", "_", name).strip("_").lower() or "room"
    body: dict = {
        "name": name,
        "visibility": "public" if public else "private",
        "preset": "public_chat" if public else "private_chat",
        "room_alias_name": alias,
    }
    return await _post("/_matrix/client/v3/createRoom", token, json=body)


async def join_room(token: str, room_id_or_alias: str) -> dict:
    """加入房间（通过 room_id 或 room alias）。返回 {room_id}。"""
    from urllib.parse import quote
    # Matrix 用冒号分隔 server name，用户可能误写 @
    fixed = room_id_or_alias.replace("@", ":", 1)
    # Matrix room ID/alias 包含 ! # : 等特殊字符，必须 URL 编码
    encoded = quote(fixed, safe="")
    return await _post(f"/_matrix/client/v3/join/{encoded}", token)

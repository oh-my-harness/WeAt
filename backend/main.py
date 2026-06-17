"""
WeAt Web 后端 — FastAPI 入口

提供:
  - POST /api/login
  - GET  /api/rooms
  - GET  /api/rooms/{room_id}/messages
  - POST /api/rooms/{room_id}/messages
  - WS   /ws

启动:
  uv run uvicorn backend.main:app --reload
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend import matrix_api
from backend.sync_loop import sync_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


# ── Pydantic models ─────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    user_id: str
    device_id: str


class SendMessageRequest(BaseModel):
    body: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    invite_code: str


# ── App ─────────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("WeAt backend starting up")
    yield
    logger.info("WeAt backend shutting down")


app = FastAPI(title="WeAt Web", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── HTTP Endpoints ──────────────────────────────────────────────────────────


@app.post("/api/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """用户名 + 密码登录 Matrix。"""
    try:
        result = await matrix_api.login(req.username, req.password)
        return LoginResponse(
            access_token=result["access_token"],
            user_id=result["user_id"],
            device_id=result.get("device_id", ""),
        )
    except Exception as e:
        logger.warning("Login failed for %s: %s", req.username, e)
        raise HTTPException(status_code=401, detail="Login failed")


@app.get("/api/rooms")
async def list_rooms(token: str = Query(...)):
    """已加入的房间列表。"""
    try:
        rooms = await matrix_api.get_rooms(token)
        return {"rooms": rooms}
    except Exception as e:
        logger.warning("Failed to get rooms: %s", e)
        raise HTTPException(status_code=500, detail="Failed to get rooms")


@app.get("/api/rooms/{room_id}/messages")
async def get_messages(room_id: str, token: str = Query(...), limit: int = Query(default=50, le=200)):
    """房间历史消息。"""
    try:
        messages = await matrix_api.get_messages(room_id, token, limit)
        return {"messages": messages}
    except Exception as e:
        logger.warning("Failed to get messages for %s: %s", room_id, e)
        raise HTTPException(status_code=500, detail="Failed to get messages")


@app.post("/api/rooms/{room_id}/messages")
async def send_message(room_id: str, req: SendMessageRequest, token: str = Query(...)):
    """发送消息。"""
    try:
        result = await matrix_api.send_message(room_id, token, req.body)
        return {"event_id": result["event_id"]}
    except Exception as e:
        logger.warning("Failed to send message to %s: %s", room_id, e)
        raise HTTPException(status_code=500, detail="Failed to send message")


@app.get("/api/me")
async def whoami(token: str = Query(...)):
    """获取当前用户信息。"""
    try:
        info = await matrix_api.get_user_info(token)
        return {"user_id": info.get("user_id", "")}
    except Exception as e:
        logger.warning("Failed to get user info: %s", e)
        raise HTTPException(status_code=401, detail="Invalid token")


# ── Admin API ──────────────────────────────────────────────────────────────

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
INVITE_CODE = os.environ.get("INVITE_CODE", "")


async def verify_admin(token: str = Query(...)):
    """验证管理员 token。"""
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="管理员模式未启用（未设置 ADMIN_TOKEN）")
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="无效的管理员令牌")


@app.post("/api/register")
async def register(req: RegisterRequest):
    """邀请码注册新用户。需设置 INVITE_CODE 环境变量。"""
    if not INVITE_CODE:
        raise HTTPException(status_code=503, detail="Registration is disabled")
    if req.invite_code != INVITE_CODE:
        raise HTTPException(status_code=403, detail="Invalid invite code")
    if len(req.username) < 3 or len(req.username) > 32:
        raise HTTPException(status_code=400, detail="Username must be 3-32 characters")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    try:
        result = await matrix_api.register_user(req.username, req.password)
        matrix_api.record_user(req.username)
        return {"user_id": result.get("user_id", "")}
    except Exception as e:
        logger.warning("Registration failed for %s: %s", req.username, e)
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/invite-code")
async def get_invite_code(_: None = Depends(verify_admin)):
    """管理员查看当前邀请码。"""
    if not INVITE_CODE:
        return {"invite_code": None, "message": "Registration disabled (INVITE_CODE not set)"}
    return {"invite_code": INVITE_CODE}


class AdminLoginRequest(BaseModel):
    admin_token: str


@app.post("/api/admin/login")
async def admin_login(req: AdminLoginRequest):
    """管理员登录：验证 ADMIN_TOKEN，返回 session token。"""
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="管理员模式未启用（未设置 ADMIN_TOKEN）")
    if req.admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="无效的管理员令牌")
    return {"token": ADMIN_TOKEN}


@app.get("/api/admin/users")
async def admin_list_users(admin_token: str = Query(...)):
    """列出所有用户（通过 Tuwunel 注册用户列表）。"""
    await verify_admin(token=admin_token)
    try:
        users = await matrix_api.get_registered_users()
        return {"users": users}
    except Exception as e:
        logger.warning("Failed to list users: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


class CreateUserRequest(BaseModel):
    username: str
    password: str


@app.post("/api/admin/users")
async def admin_create_user(req: CreateUserRequest, admin_token: str = Query(...)):
    """管理员创建用户。"""
    await verify_admin(token=admin_token)
    try:
        result = await matrix_api.register_user(req.username, req.password)
        matrix_api.record_user(req.username)
        return {"user_id": result.get("user_id", req.username)}
    except Exception as e:
        logger.warning("Failed to create user: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


class ResetPasswordRequest(BaseModel):
    username: str
    new_password: str


@app.post("/api/admin/reset-password")
async def admin_reset_password(req: ResetPasswordRequest, admin_token: str = Query(...)):
    """重置用户密码。"""
    await verify_admin(token=admin_token)
    try:
        await matrix_api.reset_password(req.username, req.new_password)
        return {"ok": True}
    except Exception as e:
        logger.warning("Failed to reset password: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/admin/users/{user_id:path}")
async def admin_delete_user(user_id: str, admin_token: str = Query(...)):
    """停用用户。"""
    await verify_admin(token=admin_token)
    try:
        await matrix_api.deactivate_user(user_id)
        return {"ok": True}
    except Exception as e:
        logger.warning("Failed to deactivate user %s: %s", user_id, e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Room Management ─────────────────────────────────────────────────────────


class CreateRoomRequest(BaseModel):
    name: str
    public: bool = False


@app.post("/api/rooms")
async def create_room(req: CreateRoomRequest, token: str = Query(...)):
    """创建房间。"""
    try:
        result = await matrix_api.create_room(token, req.name, req.public)
        return {"room_id": result.get("room_id", "")}
    except Exception as e:
        logger.warning("Failed to create room: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/rooms/{room_id:path}/join")
async def join_room(room_id: str, token: str = Query(...)):
    """加入房间。"""
    try:
        result = await matrix_api.join_room(token, room_id)
        return {"room_id": result.get("room_id", room_id)}
    except Exception as e:
        logger.warning("Failed to join room %s: %s", room_id, e)
        raise HTTPException(status_code=500, detail=str(e))


# ── WebSocket ───────────────────────────────────────────────────────────────


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str = Query(...)):
    """WebSocket 连接 — 实时消息推送。"""
    await ws.accept()

    # 验证 token 并获取 user_id
    try:
        info = await matrix_api.get_user_info(token)
        user_id = info.get("user_id", "")
    except Exception:
        await ws.send_json({"type": "error", "detail": "Invalid token"})
        await ws.close(code=4001)
        return

    send_queue: asyncio.Queue = asyncio.Queue()
    sync_manager.register_ws(user_id, token, send_queue)

    try:
        # 发送欢迎事件
        await ws.send_json({"type": "connected", "user_id": user_id})

        # 监听两个方向:
        # 1. WebSocket 接收 → 暂时不处理客户端消息（未来可用于 typing indicators）
        # 2. sync loop 推送 → 转发给 WebSocket
        receiver = asyncio.create_task(_ws_receiver(ws, user_id))
        sender = asyncio.create_task(_ws_sender(ws, send_queue))

        done, pending = await asyncio.wait(
            [receiver, sender],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
    except WebSocketDisconnect:
        logger.info("WS disconnected: %s", user_id)
    except Exception:
        logger.exception("WS error for %s", user_id)
    finally:
        sync_manager.unregister_ws(user_id, send_queue)


async def _ws_receiver(ws: WebSocket, user_id: str):
    """处理从客户端收到的 WebSocket 消息。"""
    async for _ in ws.iter_json():
        pass  # 暂时忽略客户端 WS 消息


async def _ws_sender(ws: WebSocket, queue: asyncio.Queue):
    """从队列取出事件并通过 WebSocket 发送。"""
    while True:
        msg = await queue.get()
        try:
            await ws.send_text(msg)
        except Exception:
            logger.warning("Failed to send WS message")
            break

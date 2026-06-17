import { useRef, useCallback, useEffect } from "react";

const API_BASE = "/api";

/** 存储 token 的 key */
const TOKEN_KEY = "weat_token";
const USER_KEY = "weat_user";

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function getUserId(): string | null {
  return sessionStorage.getItem(USER_KEY);
}

export function setUserId(uid: string) {
  sessionStorage.setItem(USER_KEY, uid);
}

export function clearSession() {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
  clearLLMConfig();
}

// ── LLM Config ─────────────────────────────────────────────────────────────

const LLM_BASE_URL_KEY = "weat_llm_base_url";
const LLM_MODEL_KEY = "weat_llm_model";
const LLM_API_KEY_KEY = "weat_llm_api_key";

export interface LLMConfig {
  baseUrl: string;
  model: string;
  apiKey: string;
}

export function getLLMConfig(): LLMConfig | null {
  const baseUrl = sessionStorage.getItem(LLM_BASE_URL_KEY);
  const model = sessionStorage.getItem(LLM_MODEL_KEY);
  const apiKey = sessionStorage.getItem(LLM_API_KEY_KEY);
  if (!baseUrl || !model || !apiKey) return null;
  return { baseUrl, model, apiKey };
}

export function setLLMConfig(config: LLMConfig) {
  sessionStorage.setItem(LLM_BASE_URL_KEY, config.baseUrl);
  sessionStorage.setItem(LLM_MODEL_KEY, config.model);
  sessionStorage.setItem(LLM_API_KEY_KEY, config.apiKey);
}

export function clearLLMConfig() {
  sessionStorage.removeItem(LLM_BASE_URL_KEY);
  sessionStorage.removeItem(LLM_MODEL_KEY);
  sessionStorage.removeItem(LLM_API_KEY_KEY);
}

// ── Types ──────────────────────────────────────────────────────────────────

export interface Room {
  room_id: string;
  name: string;
}

export interface MatrixMessage {
  type: string;
  content: { body: string; msgtype?: string; format?: string; formatted_body?: string };
  sender: string;
  event_id: string;
  origin_server_ts: number;
}

export interface ChatMessage {
  id: string; // 临时 ID 或 event_id
  room_id: string;
  sender: string;
  body: string;
  ts: number;
  pending: boolean; // true = 尚未确认
  failed?: boolean; // true = 发送失败
  _tempId?: string; // 乐观更新时用于替换原 temp 消息
}

// ── HTTP Client ────────────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  signal?: AbortSignal,
): Promise<T> {
  const token = getToken();
  const separator = path.includes("?") ? "&" : "?";
  const tokenParam = token ? `${separator}token=${encodeURIComponent(token)}` : "";
  const url = `${API_BASE}${path}${tokenParam}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...options.headers },
    signal,
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

// ── API Functions ──────────────────────────────────────────────────────────

export async function login(username: string, password: string) {
  const data = await apiFetch<{ access_token: string; user_id: string }>("/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  setToken(data.access_token);
  setUserId(data.user_id);
  return data;
}

export async function registerUser(
  username: string,
  password: string,
  inviteCode: string,
): Promise<{ user_id: string }> {
  const res = await fetch("/api/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password, invite_code: inviteCode }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Register failed: ${res.status}`);
  }
  return res.json();
}

export async function adminGetInviteCode(adminToken: string): Promise<{ invite_code: string | null; message?: string }> {
  const res = await fetch(`/api/invite-code?token=${encodeURIComponent(adminToken)}`);
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  return res.json();
}

export async function fetchRooms(): Promise<Room[]> {
  const data = await apiFetch<{ rooms: Room[] }>("/rooms");
  return data.rooms;
}

export async function fetchMessages(
  roomId: string,
  limit = 50,
  signal?: AbortSignal,
): Promise<MatrixMessage[]> {
  const data = await apiFetch<{ messages: MatrixMessage[] }>(
    `/rooms/${encodeURIComponent(roomId)}/messages?limit=${limit}`,
    {},
    signal,
  );
  return data.messages;
}

export async function sendMessage(
  roomId: string,
  body: string
): Promise<{ event_id: string }> {
  return apiFetch<{ event_id: string }>(
    `/rooms/${encodeURIComponent(roomId)}/messages`,
    {
      method: "POST",
      body: JSON.stringify({ body }),
    }
  );
}

// ── Admin API ──────────────────────────────────────────────────────────────

/** 管理员登录：验证 ADMIN_TOKEN 并返回 session token */
export async function adminLogin(adminToken: string): Promise<string> {
  const data = await apiFetch<{ token: string }>("/admin/login", {
    method: "POST",
    body: JSON.stringify({ admin_token: adminToken }),
  });
  return data.token;
}

/** 管理员：创建用户 */
export async function adminCreateUser(adminToken: string, username: string, password: string): Promise<string> {
  const data = await apiFetch<{ user_id: string }>(`/admin/users?admin_token=${encodeURIComponent(adminToken)}`, {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  return data.user_id;
}

/** 管理员：列出所有用户 */
export async function adminListUsers(adminToken: string): Promise<{ name: string; deactivated: boolean }[]> {
  const data = await apiFetch<{ users: { name: string; deactivated: boolean }[] }>(
    `/admin/users?admin_token=${encodeURIComponent(adminToken)}`
  );
  return data.users;
}

/** 管理员：停用用户 */
export async function adminDeleteUser(adminToken: string, userId: string): Promise<void> {
  await apiFetch<{ ok: boolean }>(
    `/admin/users/${encodeURIComponent(userId)}?admin_token=${encodeURIComponent(adminToken)}`,
    { method: "DELETE" }
  );
}

// ── Room Management ────────────────────────────────────────────────────────

export async function createRoom(name: string, pub = false): Promise<string> {
  const data = await apiFetch<{ room_id: string }>("/rooms", {
    method: "POST",
    body: JSON.stringify({ name, public: pub }),
  });
  return data.room_id;
}

export async function joinRoom(roomIdOrAlias: string): Promise<string> {
  const data = await apiFetch<{ room_id: string }>(
    `/rooms/${encodeURIComponent(roomIdOrAlias)}/join`,
    { method: "POST" }
  );
  return data.room_id;
}

// ── WebSocket Hook ─────────────────────────────────────────────────────────

const WS_RECONNECT_DELAY = 2000;

let _wsInstance: WebSocket | null = null;
let _wsReconnectTimer: ReturnType<typeof setTimeout> | null = null;

export function useWebSocket(onEvent: (data: any) => void) {
  const wsRef = useRef<WebSocket | null>(null);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const connect = useCallback(() => {
    const token = getToken();
    if (!token) return;

    // 去重：防止 React StrictMode 重复连接
    if (_wsInstance && _wsInstance.readyState === WebSocket.OPEN) {
      wsRef.current = _wsInstance;
      return;
    }
    if (_wsInstance && _wsInstance.readyState === WebSocket.CONNECTING) {
      wsRef.current = _wsInstance;
      return;
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const url = `${protocol}//${host}/ws?token=${encodeURIComponent(token)}`;

    const ws = new WebSocket(url);
    _wsInstance = ws;
    wsRef.current = ws;

    ws.onopen = () => console.log("WS connected");
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        onEventRef.current(data);
      } catch {
        console.warn("WS parse error", ev.data);
      }
    };
    ws.onclose = () => {
      _wsInstance = null;
      console.log("WS disconnected, reconnecting...");
      _wsReconnectTimer = setTimeout(() => connect(), WS_RECONNECT_DELAY);
    };
    ws.onerror = () => ws.close();
  }, []);

  const disconnect = useCallback(() => {
    if (_wsReconnectTimer) clearTimeout(_wsReconnectTimer);
    wsRef.current?.close();
    wsRef.current = null;
    _wsInstance = null;
  }, []);

  return { connect, disconnect };
}

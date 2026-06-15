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
}

// ── HTTP Client ────────────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const params = token ? `?token=${encodeURIComponent(token)}` : "";
  const url = `${API_BASE}${path}${path.includes("?") ? "&" : params.startsWith("?") ? params : ""}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...options.headers },
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

export async function fetchRooms(): Promise<Room[]> {
  const data = await apiFetch<{ rooms: Room[] }>("/rooms");
  return data.rooms;
}

export async function fetchMessages(
  roomId: string,
  limit = 50
): Promise<MatrixMessage[]> {
  const data = await apiFetch<{ messages: MatrixMessage[] }>(
    `/rooms/${encodeURIComponent(roomId)}/messages?limit=${limit}`
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

// ── WebSocket Hook ─────────────────────────────────────────────────────────

const WS_RECONNECT_DELAY = 2000;
const WS_MAX_RECONNECT = 30_000;

export function useWebSocket(onEvent: (data: any) => void) {
  const wsRef = useRef<WebSocket | null>(null);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const connect = useCallback(() => {
    const token = getToken();
    if (!token) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const url = `${protocol}//${host}/ws?token=${encodeURIComponent(token)}`;

    const ws = new WebSocket(url);
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
      console.log("WS disconnected, reconnecting...");
      setTimeout(() => connect(), WS_RECONNECT_DELAY);
    };
    ws.onerror = () => ws.close();
  }, []);

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  return { connect, disconnect };
}

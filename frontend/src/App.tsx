import { useState, useCallback, useEffect, useRef } from "react";
import {
  getToken,
  getUserId,
  clearSession,
  fetchRooms,
  ChatMessage,
  MatrixMessage,
  Room,
  useWebSocket,
} from "./api";
import LoginPage from "./LoginPage";
import RoomList from "./RoomList";
import ChatPage from "./ChatPage";

type Page = "login" | "rooms" | "chat";

export default function App() {
  const [page, setPage] = useState<Page>(
    getToken() ? "rooms" : "login"
  );
  const [rooms, setRooms] = useState<Room[]>([]);
  const [activeRoom, setActiveRoom] = useState<Room | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  // 登录成功回调
  const handleLogin = useCallback(() => {
    setPage("rooms");
    loadRooms();
  }, []);

  // 登出
  const handleLogout = useCallback(() => {
    clearSession();
    setPage("login");
    setRooms([]);
    setActiveRoom(null);
    setMessages([]);
  }, []);

  // 加载房间列表
  const loadRooms = useCallback(async () => {
    try {
      const r = await fetchRooms();
      setRooms(r);
    } catch (e) {
      console.error("Failed to load rooms", e);
    }
  }, []);

  // 选择房间
  const handleSelectRoom = useCallback((room: Room) => {
    setActiveRoom(room);
    setPage("chat");
  }, []);

  // WebSocket 事件处理
  const handleWSEvent = useCallback((data: any) => {
    if (data.type === "m.room.message" && data.room_id === activeRoom?.room_id) {
      // 检查是否已存在（去重）
      const exists = messagesRef.current.some(
        (m) => m.id === data.event_id
      );
      if (!exists) {
        const msg: ChatMessage = {
          id: data.event_id,
          room_id: data.room_id,
          sender: data.sender,
          body: data.content?.body || "",
          ts: data.origin_server_ts || Date.now(),
          pending: false,
        };
        setMessages((prev) => [...prev, msg]);
      }
    }
  }, [activeRoom?.room_id]);

  const ws = useWebSocket(handleWSEvent);

  // 登录后连接 WS
  useEffect(() => {
    if (getToken()) {
      ws.connect();
      loadRooms();
    }
    return () => ws.disconnect();
  }, []);

  // 当加载消息时，标记 loading 状态
  const handleLoadingMessages = useCallback((loading: boolean) => {
    setLoading(loading);
  }, []);

  // 切换房间时更新 WS handler 使用的房间 ID
  const handleAddMessage = useCallback((msg: ChatMessage) => {
    setMessages((prev) => {
      const idx = prev.findIndex((m) => m.id === msg.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = msg;
        return next;
      }
      return [...prev, msg];
    });
  }, []);

  const handleBackToRooms = useCallback(() => {
    setActiveRoom(null);
    setMessages([]);
    setPage("rooms");
  }, []);

  if (page === "login") {
    return <LoginPage onLogin={handleLogin} />;
  }

  return (
    <div className="flex h-full">
      {/* 桌面侧栏 */}
      <aside className="hidden md:flex md:flex-col w-72 bg-white border-r shrink-0">
        <RoomList
          rooms={rooms}
          activeRoom={activeRoom}
          onSelect={handleSelectRoom}
          onLogout={handleLogout}
          onRefresh={loadRooms}
        />
      </aside>

      {/* 聊天主体 */}
      <main className="flex-1 flex flex-col min-w-0">
        {activeRoom ? (
          <ChatPage
            room={activeRoom}
            messages={messages}
            onAddMessage={handleAddMessage}
            onBack={handleBackToRooms}
          />
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-400 text-lg">
            选择一个房间开始聊天
          </div>
        )}
      </main>

      {/* 手机底部导航 */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t z-10">
        <RoomList
          compact
          rooms={rooms}
          activeRoom={activeRoom}
          onSelect={handleSelectRoom}
          onLogout={handleLogout}
          onRefresh={loadRooms}
        />
      </nav>
    </div>
  );
}

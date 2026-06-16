import { useState, useCallback, useEffect, useRef } from "react";
import {
  getToken,
  clearSession,
  fetchRooms,
  createRoom,
  joinRoom,
  ChatMessage,
  Room,
  useWebSocket,
} from "./api";
import LoginPage from "./LoginPage";
import RoomList from "./RoomList";
import ChatPage from "./ChatPage";
import Settings from "./Settings";
import AdminPanel from "./AdminPanel";

const ADMIN_TOKEN_KEY = "weat_admin_token";

function getAdminToken(): string | null {
  return sessionStorage.getItem(ADMIN_TOKEN_KEY);
}

function clearAdminToken() {
  sessionStorage.removeItem(ADMIN_TOKEN_KEY);
}

type Page = "login" | "rooms" | "chat" | "admin";

export default function App() {
  const isAdmin = !!getAdminToken();
  const [page, setPage] = useState<Page>(
    isAdmin ? "admin" : getToken() ? "rooms" : "login"
  );
  const [rooms, setRooms] = useState<Room[]>([]);
  const [activeRoom, setActiveRoom] = useState<Room | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [showSettings, setShowSettings] = useState(false);
  const [showAdmin, setShowAdmin] = useState(false);
  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  const handleLogin = useCallback(() => {
    // Check if this was an admin login
    if (getAdminToken()) {
      setPage("admin");
    } else {
      setPage("rooms");
      loadRooms();
    }
  }, []);

  const handleLogout = useCallback(() => {
    clearSession();
    setPage("login");
    setRooms([]);
    setActiveRoom(null);
    setMessages([]);
  }, []);

  const handleAdminLogout = useCallback(() => {
    clearAdminToken();
    setPage("login");
  }, []);

  const loadRooms = useCallback(async () => {
    try {
      const r = await fetchRooms();
      setRooms(r);
    } catch (e) {
      console.error("Failed to load rooms", e);
    }
  }, []);

  const handleSelectRoom = useCallback((room: Room) => {
    setActiveRoom(room);
    setPage("chat");
  }, []);

  const handleWSEvent = useCallback((data: any) => {
    if (data.type === "m.room.message" && data.room_id === activeRoom?.room_id) {
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
        setMessages((prev) => {
          if (prev.some((m) => m.id === data.event_id)) return prev;
          return [...prev, msg];
        });
      }
    }
  }, [activeRoom?.room_id]);

  const ws = useWebSocket(handleWSEvent);

  useEffect(() => {
    if (getToken()) {
      ws.connect();
      loadRooms();
    }
    return () => ws.disconnect();
  }, []);

  const handleAddMessage = useCallback((msg: ChatMessage) => {
    setMessages((prev) => {
      const withoutTemp = msg._tempId
        ? prev.filter((m) => m.id !== msg._tempId)
        : prev;
      const idx = withoutTemp.findIndex((m) => m.id === msg.id);
      if (idx >= 0) {
        const next = [...withoutTemp];
        next[idx] = msg;
        return next;
      }
      return [...withoutTemp, msg];
    });
  }, []);

  const handleBackToRooms = useCallback(() => {
    setActiveRoom(null);
    setMessages([]);
    setPage("rooms");
  }, []);

  const handleCreateRoom = useCallback(async (name: string, pub: boolean) => {
    await createRoom(name, pub);
    await loadRooms();
  }, [loadRooms]);

  const handleJoinRoom = useCallback(async (roomIdOrAlias: string) => {
    await joinRoom(roomIdOrAlias);
    await loadRooms();
  }, [loadRooms]);

  if (page === "login") {
    return <LoginPage onLogin={handleLogin} />;
  }

  // 管理员控制台（独立页面，不走 Matrix 登录）
  if (page === "admin") {
    return (
      <div className="flex flex-col h-full">
        <header className="flex items-center gap-2 px-4 py-3 border-b bg-white shrink-0">
          <h1 className="font-semibold flex-1">WeAt 管理员控制台</h1>
          <button
            onClick={handleAdminLogout}
            className="text-sm text-gray-500 hover:text-red-500"
          >
            退出
          </button>
        </header>
        <div className="flex-1 overflow-y-auto">
          <AdminPanel onClose={() => {}} />
        </div>
      </div>
    );
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
          onSettings={() => setShowSettings(true)}
          onAdmin={() => setShowAdmin(true)}
          onCreateRoom={handleCreateRoom}
          onJoinRoom={handleJoinRoom}
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

      {/* 设置弹窗 */}
      {showSettings && <Settings onClose={() => setShowSettings(false)} />}

      {/* 管理弹窗 */}
      {showAdmin && <AdminPanel onClose={() => setShowAdmin(false)} />}
    </div>
  );
}

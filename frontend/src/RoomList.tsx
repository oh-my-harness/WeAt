import { Room } from "./api";

interface Props {
  rooms: Room[];
  activeRoom: Room | null;
  onSelect: (room: Room) => void;
  onLogout: () => void;
  onRefresh: () => void;
  onSettings?: () => void;
  onAdmin?: () => void;
  compact?: boolean;
}

export default function RoomList({
  rooms,
  activeRoom,
  onSelect,
  onLogout,
  onRefresh,
  onSettings,
  onAdmin,
  compact,
}: Props) {
  if (compact) {
    // 手机底部 Tab 导航：只显示房间名首字母
    return (
      <div className="flex overflow-x-auto px-2 py-1 gap-1">
        {rooms.map((r) => {
          const label = r.name || r.room_id.slice(0, 8);
          const active = activeRoom?.room_id === r.room_id;
          return (
            <button
              key={r.room_id}
              onClick={() => onSelect(r)}
              className={`shrink-0 w-12 h-12 rounded-full text-sm font-medium flex items-center justify-center ${
                active
                  ? "bg-blue-600 text-white"
                  : "text-gray-600 hover:bg-gray-100"
              }`}
              title={r.name || r.room_id}
            >
              {label.charAt(0).toUpperCase()}
            </button>
          );
        })}
      </div>
    );
  }

  // 桌面侧栏
  return (
    <>
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <h2 className="font-semibold text-gray-800">房间</h2>
        <div className="flex gap-1">
          <button
            onClick={onAdmin}
            className="text-gray-400 hover:text-green-600 p-1 rounded transition-colors"
            title="用户管理"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          </button>
          <button
            onClick={onSettings}
            className="text-gray-400 hover:text-blue-600 p-1 rounded transition-colors"
            title="设置"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </button>
          <button
            onClick={onRefresh}
            className="text-gray-400 hover:text-blue-600 p-1 rounded transition-colors"
            title="刷新"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
          <button
            onClick={onLogout}
            className="text-gray-400 hover:text-red-500 p-1 rounded transition-colors"
            title="退出"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {rooms.length === 0 && (
          <div className="text-gray-400 text-sm text-center py-8">
            暂未加入任何房间
          </div>
        )}
        {rooms.map((r) => {
          const label = r.name || r.room_id.slice(0, 12) + "...";
          const active = activeRoom?.room_id === r.room_id;
          return (
            <button
              key={r.room_id}
              onClick={() => onSelect(r)}
              className={`w-full text-left px-4 py-3 border-b border-gray-50 hover:bg-gray-50 transition-colors ${
                active ? "bg-blue-50 border-l-3 border-l-blue-600" : ""
              }`}
            >
              <div className="font-medium text-sm truncate">{label}</div>
              <div className="text-xs text-gray-400 truncate mt-0.5">
                {r.room_id}
              </div>
            </button>
          );
        })}
      </div>
    </>
  );
}

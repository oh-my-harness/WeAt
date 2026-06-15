import type { Tool } from "../agent/types";
import { fetchMessages } from "../api";

/** 获取房间历史消息的工具 */
export function createGetRoomHistoryTool(roomId: string): Tool<{ limit?: number }> {
  return {
    definition: {
      name: "get_room_history",
      description: "获取当前房间的最近聊天历史消息",
      parameters: {
        type: "object",
        properties: {
          limit: {
            type: "number",
            description: "获取的消息条数，默认 30",
          },
        },
        required: [],
      },
    },
    async execute(params) {
      const limit = params.limit ?? 30;
      try {
        const msgs = await fetchMessages(roomId, limit);
        // 格式化为可读文本
        const lines = msgs
          .reverse() // messages 返回从旧到新，反转成倒序
          .map((m) => {
            const sender = m.sender.split(":")[0].replace("@", "");
            const body = m.content?.body || "";
            return `[${sender}] ${body}`;
          })
          .join("\n");
        return lines || "（暂无消息）";
      } catch (err: any) {
        return `Error fetching history: ${err.message}`;
      }
    },
  };
}

/**
 * WeAt 浏览器端 Agent — 主循环
 *
 * 受 pi 的 agent-loop.ts 启发，极度简化：
 * 1. 构造请求消息
 * 2. streamLLM → 获取 tool calls
 * 3. 执行 tool → 结果放回消息
 * 4. 继续循环（maxTurns 限制）
 */

import type {
  AgentConfig,
  AgentEvent,
  Message,
  AssistantMessage,
  ToolCall,
} from "./types";
import { streamLLM } from "./llm";

export { type AgentConfig, type AgentEvent, type Message } from "./types";

export type EventCallback = (event: AgentEvent) => void;

/**
 * 运行 Agent。
 * 传入用户消息，返回生成的回复文本（最终输出）。
 * 期间通过 onEvent 回调告知 UI 发生了什么。
 */
export async function runAgent(
  config: AgentConfig,
  userMessage: string,
  onEvent: EventCallback,
  signal?: AbortSignal,
): Promise<string> {
  const maxTurns = config.maxTurns ?? 5;
  const messages: Message[] = [
    { role: "user", content: userMessage },
  ];

  onEvent({ type: "agent_start" });
  onEvent({ type: "message", message: messages[0] });

  for (let turn = 0; turn < maxTurns; turn++) {
    // Step 1: Call LLM
    onEvent({ type: "thinking", text: "思考中…" });

    let response: AssistantMessage;
    try {
      response = await streamLLM(
        config.llm,
        config.systemPrompt,
        messages,
        config.tools.map((t) => t.definition),
        signal,
        // onDelta
        (text) => onEvent({ type: "thinking", text }),
        // onToolCalls
        (calls) => {
          onEvent({ type: "message", message: { role: "assistant", content: response?.content || "", toolCalls: calls, stopReason: "toolUse" } });
        },
      );
    } catch (err: any) {
      onEvent({ type: "error", message: err.message || "LLM call failed" });
      return `Error: ${err.message}`;
    }

    messages.push(response);

    // No tool calls → 返回文本
    if (!response.toolCalls || response.toolCalls.length === 0) {
      onEvent({ type: "agent_end" });
      return response.content;
    }

    // Step 2: Execute tools
    for (const tc of response.toolCalls) {
      const tool = config.tools.find((t) => t.definition.name === tc.function.name);
      if (!tool) {
        const errMsg = `Unknown tool: ${tc.function.name}`;
        messages.push({
          role: "tool",
          toolCallId: tc.id,
          content: errMsg,
        });
        onEvent({ type: "error", message: errMsg });
        continue;
      }

      let args: Record<string, unknown>;
      try {
        args = JSON.parse(tc.function.arguments);
      } catch {
        args = {};
      }

      onEvent({ type: "tool_start", toolName: tc.function.name });

      let result: string;
      try {
        result = await tool.execute(args, { signal });
      } catch (err: any) {
        result = `Error: ${err.message}`;
      }

      onEvent({ type: "tool_end", toolName: tc.function.name, result });

      messages.push({
        role: "tool",
        toolCallId: tc.id,
        content: result,
      });
    }
  }

  // 超过 maxTurns，返回最后一次 assistant 回复
  const last = [...messages].reverse().find((m) => m.role === "assistant");
  onEvent({ type: "agent_end" });
  return (last as AssistantMessage)?.content || "Agent exceeded max turns";
}

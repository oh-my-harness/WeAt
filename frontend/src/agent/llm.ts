/**
 * LLM API 调用 — 直接 fetch OpenAI 兼容的 chat completions API
 *
 * 支持流式和非流式两种模式。
 */

import type { LLMConfig, Message, ToolCall, ToolDefinition, AssistantMessage } from "./types";

interface ChatCompletionMessage {
  role: "system" | "user" | "assistant" | "tool";
  content: string;
  tool_calls?: Array<{
    id: string;
    type: "function";
    function: { name: string; arguments: string };
  }>;
  tool_call_id?: string;
}

interface ChatCompletionRequest {
  model: string;
  messages: ChatCompletionMessage[];
  tools?: Array<{
    type: "function";
    function: {
      name: string;
      description: string;
      parameters: Record<string, unknown>;
    };
  }>;
  stream: boolean;
  max_tokens: number;
  temperature: number;
}

interface ChatCompletionChunk {
  choices: Array<{
    delta: {
      content?: string | null;
      tool_calls?: Array<{
        index: number;
        id?: string;
        type?: "function";
        function?: { name?: string; arguments?: string };
      }>;
    };
    finish_reason: string | null;
  }>;
}

/** 将 WeAt 内部消息转为 OpenAI 格式 */
function toOpenAIMessages(messages: Message[]): ChatCompletionMessage[] {
  return messages.map((m) => {
    switch (m.role) {
      case "user":
        return { role: "user", content: m.content };
      case "assistant":
        return {
          role: "assistant",
          content: m.content,
          tool_calls: m.toolCalls?.map((tc) => ({
            id: tc.id,
            type: "function" as const,
            function: { name: tc.function.name, arguments: tc.function.arguments },
          })),
        };
      case "tool":
        return { role: "tool", content: m.content, tool_call_id: m.toolCallId };
    }
  });
}

/**
 * 调 LLM API（流式）
 * 返回事件回调：content delta 和 tool_calls
 */
export async function streamLLM(
  config: LLMConfig,
  systemPrompt: string,
  messages: Message[],
  tools: ToolDefinition[],
  signal?: AbortSignal,
  onDelta?: (text: string) => void,
  onToolCalls?: (calls: ToolCall[]) => void,
  onThinking?: (text: string) => void,
): Promise<AssistantMessage> {
  const url = `${config.baseUrl.replace(/\/+$/, "")}/chat/completions`;

  const body: ChatCompletionRequest = {
    model: config.model,
    messages: [
      { role: "system", content: systemPrompt },
      ...toOpenAIMessages(messages),
    ],
    tools: tools.length > 0
      ? tools.map((t) => ({
          type: "function" as const,
          function: {
            name: t.name,
            description: t.description,
            parameters: t.parameters as Record<string, unknown>,
          },
        }))
      : undefined,
    stream: true,
    max_tokens: 4096,
    temperature: 0.7,
  };

  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${config.apiKey}`,
    },
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`LLM API ${res.status}: ${text}`);
  }

  // 解析 SSE 流
  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";
  let content = "";
  let toolCallsAccum: ToolCall[] = [];

  const parseLine = (line: string) => {
    if (!line.startsWith("data: ")) return;
    const data = line.slice(6).trim();
    if (data === "[DONE]") return;

    try {
      const chunk: ChatCompletionChunk = JSON.parse(data);
      const choice = chunk.choices?.[0];
      if (!choice) return;

      const delta = choice.delta;

      // 处理 text delta
      if (delta?.content) {
        content += delta.content;
        onDelta?.(delta.content);
      }

      // 处理 tool_calls delta
      if (delta?.tool_calls) {
        for (const tc of delta.tool_calls) {
          const idx = tc.index;

          // 如果这个 index 还没有，初始化它
          if (!toolCallsAccum[idx]) {
            const id = tc.id || `call_${idx}_${Date.now()}`;
            toolCallsAccum[idx] = {
              id,
              type: "function",
              function: { name: "", arguments: "" },
            };
          }

          if (tc.id) toolCallsAccum[idx].id = tc.id;
          if (tc.function?.name) toolCallsAccum[idx].function.name += tc.function.name;
          if (tc.function?.arguments) toolCallsAccum[idx].function.arguments += tc.function.arguments;
        }
      }
    } catch {
      // 忽略 parse 错误
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      parseLine(line);
    }
  }

  // 处理 buffer 剩余
  if (buffer.trim()) {
    parseLine(buffer);
  }

  const finishReason = determineStopReason(toolCallsAccum);
  const finalCalls = toolCallsAccum.length > 0 ? toolCallsAccum : undefined;

  if (finalCalls) {
    onToolCalls?.(finalCalls);
  }

  return {
    role: "assistant",
    content,
    toolCalls: finalCalls,
    stopReason: finishReason,
  };
}

/**
 * 非流式调用（用于简单的 completion，如 summarize）
 */
export async function completeLLM(
  config: LLMConfig,
  systemPrompt: string,
  messages: Message[],
  signal?: AbortSignal,
): Promise<string> {
  const url = `${config.baseUrl.replace(/\/+$/, "")}/chat/completions`;

  const body: ChatCompletionRequest = {
    model: config.model,
    messages: [
      { role: "system", content: systemPrompt },
      ...toOpenAIMessages(messages),
    ],
    stream: false,
    max_tokens: 4096,
    temperature: 0.7,
  };

  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${config.apiKey}`,
    },
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`LLM API ${res.status}: ${text}`);
  }

  const data = await res.json();
  return data.choices?.[0]?.message?.content || "";
}

function determineStopReason(toolCalls: ToolCall[]): AssistantMessage["stopReason"] {
  if (toolCalls.length > 0) return "toolUse";
  return "stop";
}

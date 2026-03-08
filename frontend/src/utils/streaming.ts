import type { ChatSSEEvent } from "../handlers/chatHandler";
import type { ChatMessage, StreamMetrics } from "../types";
import type { CurrentChatType } from "../store/SidebarContext";

export type { StreamMetrics };

export function createMessageStreamer(params: {
  setCurrentChat: (updater: (prev: CurrentChatType | null) => CurrentChatType | null) => void;
  messageId: string;
  onComplete?: (metrics: StreamMetrics) => void;
}) {
  const { setCurrentChat, messageId, onComplete } = params;

  let t0 = 0;
  let firstTokenAt: number | null = null;
  let endAt: number | null = null;

  const markStart = () => {
    t0 = performance.now();
    firstTokenAt = null;
    endAt = null;
  };

  const computeMetrics = (): StreamMetrics => {
    const ttft = firstTokenAt ? Math.round(firstTokenAt - t0) : undefined;
    const total = Math.round((endAt ?? performance.now()) - t0);
    return { timeToFirstToken: ttft, totalResponseTime: total };
  };

  const onEvent = (evt: ChatSSEEvent) => {
    if (!evt) return;

    if (evt.event === "final_answer") {
      let chunk: string = evt.data.chunk ?? "";
      setCurrentChat((prevChat: CurrentChatType | null) => {
        if (!prevChat) return prevChat;
        const updated = prevChat.allMessages.map((m: ChatMessage) => {
          if (m.id !== messageId) return m;
          let buffer = m._streamBuffer || "";
          if (!m._finalAnswerStarted) {
            if (!firstTokenAt) firstTokenAt = performance.now();
            // remove a single leading code fence if present
            chunk = chunk.replace(/^```[a-zA-Z0-9]*\n?/, "");
            buffer = chunk;
            return {
              ...m,
              botMessage: buffer,
              statusMessage: undefined,
              streaming: true,
              _finalAnswerStarted: true,
              _fenceStripped: chunk !== (evt.data.chunk ?? ""),
              _streamBuffer: buffer,
            };
          } else {
            // If fence was split across chunks, strip leftover language tag
            if (m._fenceStripped && !m._fenceCleanDone) {
              chunk = chunk.replace(/^[a-zA-Z0-9]*\n?/, "");
            }
            // remove trailing fence, if any
            chunk = chunk.replace(/```$/, "");
            buffer += chunk;
            return {
              ...m,
              botMessage: buffer,
              streaming: true,
              _streamBuffer: buffer,
              _fenceCleanDone: true,
            };
          }
        });
        return { ...prevChat, allMessages: updated };
      });
    } else if (evt.event === "status") {
      setCurrentChat((prevChat: CurrentChatType | null) => {
        if (!prevChat) return prevChat;
        return {
          ...prevChat,
          allMessages: prevChat.allMessages.map((m: ChatMessage) => {
            if (m.id !== messageId) return m;
            if (m._finalAnswerStarted || m._finalAnswerDone) return m;
            return {
              ...m,
              botMessage: "",
              statusMessage: evt.data?.message || "Processing...",
              streaming: true,
            };
          }),
        };
      });
    } else if (evt.event === "error") {
      endAt = performance.now();
      const metrics = computeMetrics();
      const serverTtft = evt.data?.time_to_first_token_ms as number | undefined;
      const serverTotal = evt.data?.total_response_time_ms as number | undefined;
      const serverModelId = evt.data?.model_id as string | undefined;
      const serverProviderType = evt.data?.provider_type as string | undefined;
      const mergedMetrics: StreamMetrics = {
        ...metrics,
        ...(serverTtft != null && { timeToFirstToken: serverTtft }),
        ...(serverTotal != null && { totalResponseTime: serverTotal }),
        ...(serverModelId != null && { modelId: serverModelId }),
        ...(serverProviderType != null && { providerType: serverProviderType }),
      };
      setCurrentChat((prevChat: CurrentChatType | null) => {
        if (!prevChat) return prevChat;
        return {
          ...prevChat,
          allMessages: prevChat.allMessages.map((m: ChatMessage) => {
            if (m.id !== messageId) return m;
            return {
              ...m,
              botMessage: m.botMessage || (evt.data?.message as string) || "Something went wrong. Please try again.",
              statusMessage: undefined,
              streaming: false,
              _finalAnswerDone: true,
              responseMetrics: mergedMetrics,
              respondedAt: new Date().toISOString(),
              ...(serverModelId != null && { modelId: serverModelId }),
              ...(serverProviderType != null && { providerType: serverProviderType }),
            };
          }),
        };
      });
      onComplete?.(mergedMetrics);
    } else if (evt.event === "complete") {
      endAt = performance.now();
      const metrics = computeMetrics();
      const realMessageId = evt.data?.message_id as string | undefined;
      const serverTtft = evt.data?.time_to_first_token_ms as number | undefined;
      const serverTotal = evt.data?.total_response_time_ms as number | undefined;
      const serverModelId = evt.data?.model_id as string | undefined;
      const serverProviderType = evt.data?.provider_type as string | undefined;
      const mergedMetrics: StreamMetrics = {
        ...metrics,
        ...(serverTtft != null && { timeToFirstToken: serverTtft }),
        ...(serverTotal != null && { totalResponseTime: serverTotal }),
        ...(serverModelId != null && { modelId: serverModelId }),
        ...(serverProviderType != null && { providerType: serverProviderType }),
      };
      setCurrentChat((prevChat: CurrentChatType | null) => {
        if (!prevChat) return prevChat;
        return {
          ...prevChat,
          allMessages: prevChat.allMessages.map((m: ChatMessage) => {
            if (m.id !== messageId) return m;
            return {
              ...m,
              id: realMessageId || m.id,
              streaming: false,
              _finalAnswerDone: true,
              responseMetrics: mergedMetrics,
              respondedAt: new Date().toISOString(),
              ...(serverModelId != null && { modelId: serverModelId }),
              ...(serverProviderType != null && { providerType: serverProviderType }),
            };
          }),
        };
      });
      onComplete?.(mergedMetrics);
    }
  };

  return { markStart, onEvent, getMetrics: computeMetrics };
}

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
              _streamBuffer: buffer,
            };
          } else {
            // remove trailing fence, if any
            chunk = chunk.replace(/```$/, "");
            buffer += chunk;
            return {
              ...m,
              botMessage: buffer,
              streaming: true,
              _streamBuffer: buffer,
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
    } else if (evt.event === "complete") {
      endAt = performance.now();
      const metrics = computeMetrics();
      const realMessageId = evt.data?.message_id as string | undefined;
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
              responseMetrics: metrics,
            };
          }),
        };
      });
      onComplete?.(metrics);
    }
  };

  return { markStart, onEvent, getMetrics: computeMetrics };
}

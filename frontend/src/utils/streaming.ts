import type { ChatSSEEvent } from "../handlers/chatHandler";

export type StreamMetrics = {
  timeToFirstToken?: number;
  totalResponseTime: number;
};

export function createMessageStreamer(params: {
  setCurrentChat: (updater: (prev: any) => any) => void;
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
      setCurrentChat((prevChat: any) => {
        const updated = prevChat?.allMessages?.map((m: any) => {
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
      setCurrentChat((prevChat: any) => ({
        ...prevChat,
        allMessages: prevChat?.allMessages?.map((m: any) => {
          if (m.id !== messageId) return m;
          if (m._finalAnswerStarted || m._finalAnswerDone) return m;
          return {
            ...m,
            botMessage: evt.data?.message || "",
            streaming: true,
          };
        }),
      }));
    } else if (evt.event === "complete") {
      endAt = performance.now();
      const metrics = computeMetrics();
      setCurrentChat((prevChat: any) => ({
        ...prevChat,
        allMessages: prevChat?.allMessages?.map((m: any) => {
          if (m.id !== messageId) return m;
          return {
            ...m,
            streaming: false,
            _finalAnswerDone: true,
            responseMetrics: metrics,
          };
        }),
      }));
      onComplete?.(metrics);
    }
  };

  return { markStart, onEvent, getMetrics: computeMetrics };
}

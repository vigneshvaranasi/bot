import { BE_URL } from "../config/config";

export type ChatSSEEvent = { event: string; data: any; label?: string };

export const newMessageHandler = async (
  chatId: string | null,
  prompt: string,
  token: string,
  onEvent?: (evt: ChatSSEEvent) => void
) => {
  const headers = new Headers();
  headers.append("Authorization", `Bearer ${token}`);
  headers.append("Content-Type", "application/json");
  const response = await fetch(`${BE_URL}/chats/prompt`, {
    method: "POST",
    headers,
    body: JSON.stringify({ chatId, prompt }),
  });

  if (!response.ok) {
    throw new Error("Failed to send message");
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("text/event-stream") && response.body) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let finalPayload: any = null;
    // state for progressive / de-duplicated UX
    let lastLabelEmitted: string | undefined;
    let lastEventType: string | undefined;

    const flushEvents = () => {
      const parts = buffer.split(/\n\n/);
      buffer = parts.pop() || "";
      for (const part of parts) {
        const lines = part.split(/\n/);
        let event = "message";
        const dataLines: string[] = [];
        for (const line of lines) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
        }
        const dataRaw = dataLines.join("\n");
        let parsed: any = dataRaw;
        try { parsed = JSON.parse(dataRaw); } catch { }
        let label: string | undefined;
        if ((event === 'status' && parsed?.phase && (parsed.phase === 'agent:start' || parsed.phase === 'agent:end')) ||
            (event === 'agent:start' || event === 'agent:end') ||
            (typeof parsed === 'string' && (parsed === 'agent:start' || parsed === 'agent:end'))) {
          return;
        }

        if (event === "status") {
          if (typeof parsed === "string") {
            label = parsed;
          } else if (parsed?.phase) {
            const phase = parsed.phase;
            if (['crew:start', 'agent:assigned', 'task:started', 'agent:started'].includes(phase)) {
              label = "Setting up the specialists";
            } else if (phase === 'task:evaluated' || phase === 'agent:completed' || phase === 'task:completed' || phase === 'crew:end' || phase === 'persistence:saving' || phase === 'persistence:done') {
              label = undefined;
            } else if (phase === 'title:generating') {
              label = "Creating a descriptive title";
            } else if (phase === 'title:done') {
              label = "Title created successfully";
            } else if (phase === 'summary:generating') {
              label = "Summarizing the conversation";
            } else if (phase === 'summary:done') {
              label = "Summary saved";
            } else {
              if (parsed.label) {
                label = parsed.label;
                if (parsed.index && parsed.total) {
                  label += ` (${parsed.index}/${parsed.total})`;
                }
              } else {
                label = parsed.phase.replace(/:/g, " → ");
              }
            }
          }
        } else if (event === "error") {
          label = `Error: ${typeof parsed === "string" ? parsed : JSON.stringify(parsed)}`;
        } else if (event === "result") {
          try { finalPayload = typeof parsed === "string" ? JSON.parse(parsed) : parsed; } catch { finalPayload = { error: "Malformed result" }; }
        } else if (event === "answer_stream") {
          if (typeof parsed === "object" && parsed.text) {
            if (onEvent) {
              onEvent({ 
                event: "answer_stream", 
                data: { text: parsed.text },
                label: parsed.text
              });
            }
            return;
          }
        } else if (event === "end") {
          if (onEvent) {
            onEvent({ event: "answer_stream_done", data: null });
          }
        } else {
          if (event === "tool:start") {
            if (parsed?.tool === 'qdrant') {
              label = parsed.label;
            } else if (parsed?.tool === 'analysis') {
              label = parsed.label;
            } else {
              if (parsed?.label) {
                label = parsed.label;
              } else {
                const tool = parsed?.tool;
                label = `Starting ${tool || 'tool'}...`;
              }
            }
          } else if (event === "tool:results") {
            if (parsed?.tool === 'qdrant') {
              const cnt = parsed?.count;
              label = `Found ${cnt} relevant incident${cnt === 1 ? '' : 's'}`;
            } else if (parsed?.tool === 'analysis') {
              const cnt = parsed?.count;
              label = `Analyzed ${cnt} incidents`;
            } else {
              if (parsed?.label) {
                label = parsed.label;
              } else {
                const cnt = parsed?.count;
                if (typeof cnt === "number") {
                  label = `Found ${cnt} relevant incident${cnt === 1 ? '' : 's'}.`;
                }
              }
            }
          } else if (event === "tool:end") {
            if (parsed?.tool === 'qdrant') {
              label = parsed.label;
            } else if (parsed?.tool === 'analysis') {
              label = parsed.label;
            } else {
              if (parsed?.label) {
                label = parsed.label;
              } else {
                const tool = parsed?.tool;
                label = `${tool || 'Tool'} completed successfully.`;
              }
            }
          }
        }
        const critical = event === 'error' || event === 'result' || event === 'end';
        if (onEvent && (label || critical)) {
          if (!critical && label && label === lastLabelEmitted && event === lastEventType) {
          } 
          else {
            if (label) lastLabelEmitted = label;
            lastEventType = event;
            // console.log('SSE Event:', event, parsed, label);
            onEvent({ event, data: parsed, label });
          }
        }
      }
    };

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      flushEvents();
    }
    // flush all
    if (buffer) {
      buffer += "\n\n";
      flushEvents();
    }

    if (finalPayload) return finalPayload;
    throw new Error("No result received from stream");
  }

  const data = await response.json();
  return data;
};

export const getAllMyChats = async (token: string) => {
  const headers = new Headers();
  headers.append("Authorization", `Bearer ${token}`);
  headers.append("Content-Type", "application/json");

  const response = await fetch(`${BE_URL}/chats/my-chats`, {
    method: "GET",
    headers,
  });

  if (!response.ok) {
    throw new Error("Failed to fetch chats");
  }

  const data = await response.json();
  return data;
};  

export const getChatMessagesById = async (token: string, chatId: string) => {
  const headers = new Headers();
  headers.append("Authorization", `Bearer ${token}`);
  headers.append("Content-Type", "application/json");

  const response = await fetch(`${BE_URL}/chats/messages/${chatId}`, {
    method: "GET",
    headers,
  });

  if (!response.ok) {
    throw new Error("Failed to fetch messages");
  }

  const data = await response.json();
  return data.messages;
};
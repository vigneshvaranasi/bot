import { BE_URL } from "../config/config";

export type ChatSSEEvent = { event: string; data: any; label?: string };

export const newMessageHandler = async (
  chatId: string | null,
  prompt: string,
  token: string,
  onEvent?: (evt: ChatSSEEvent) => void
) => {
  console.log(JSON.stringify({ chatId, prompt }));
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

    const flushEvents = () => {
      const parts = buffer.split(/\n\n/);
      buffer = parts.pop() || "";
      for (const part of parts) {
        const lines = part.split(/\n/);
        let event = "message";
        const dataLines: string[] = [];
        for (const line of lines) {
          if (line.startsWith("event:")) {
            event = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            dataLines.push(line.slice(5).trim());
          }
        }
        const dataRaw = dataLines.join("\n");
        let parsed: any = dataRaw;
        try {
          parsed = JSON.parse(dataRaw);
        } catch {
          // todo
        }

        let label: string | undefined;
        if (event === "status") {
          if (typeof parsed === "string") {
            label = parsed;
          } else if (parsed?.phase) {
            const phase = String(parsed.phase);
            if (phase.includes("crew:start")) label = "Planning...";
            else if (phase.includes("crew:end")) label = "Finalizing...";
            else if (phase.includes("task:start")) label = "Task started...";
            else if (phase.includes("task:end")) label = "Task completed.";
            else if (phase.includes("agent:start")) label = "Agent working...";
            else if (phase.includes("agent:end")) label = "Agent finished.";
          }
          console.log(`[SSE] ${typeof parsed === "string" ? parsed : JSON.stringify(parsed)}`);
        } else if (event === "error") {
          label = `Error: ${typeof parsed === "string" ? parsed : JSON.stringify(parsed)}`;
          console.error(`[SSE] error: ${JSON.stringify(parsed)}`);
        } else if (event === "result") {
          try {
            finalPayload = typeof parsed === "string" ? JSON.parse(parsed) : parsed;
          } catch {
            finalPayload = { error: "Malformed result" };
          }
        } else if (event === "end") {
          console.log("[SSE] end");
        } else {
          if (event === "tool:start") {
            const tool = parsed?.tool;
            if (tool === "qdrant") label = "Searching incidents...";
            else if (tool === "analysis") label = "Analyzing incident data...";
          } else if (event === "tool:results") {
            const cnt = parsed?.count;
            if (typeof cnt === "number") label = `Found ${cnt} incident${cnt === 1 ? "" : "s"}...`;
          } else if (event === "tool:end") {
            // todo
          }
          console.log(`[SSE:${event}] ${typeof parsed === "string" ? parsed : JSON.stringify(parsed)}`);
        }

        if (onEvent && (label || event === "result" || event === "end" || event === "error")) {
          onEvent({ event, data: parsed, label });
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

export const getChatMessagesById = async (token: string,chatId:string) => {
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


export const handleRetry = async (
  messageId: string,
  oldPrompt: string,
  user: { token: string } | null,
  currentChat: any,
  setCurrentChat: (chat: any) => void,
) => {
  if (!user || !currentChat) return;

  const updatedMessages = currentChat.allMessages.map((msg: any) =>
    msg.id === messageId ? { ...msg, isRetrying: true } : msg
  );
  setCurrentChat({ ...currentChat, allMessages: updatedMessages });

  try {
    const response = await fetch(`${BE_URL}/chats/retry`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${user.token}`,
      },
      body: JSON.stringify({
        chat_id: currentChat.chatId,
        message_id: messageId,
        prompt: oldPrompt,
      }),
    });

    if (!response.ok) throw new Error("Retry failed");

    const reader = response.body?.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let finalBotMessage = "";

    const processChunk = (chunk: string) => {
      buffer += chunk;
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";
      for (const part of parts) {
        const lines = part.split("\n");
        let event = "";
        let data = "";
        for (const line of lines) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) data = line.slice(5).trim();
        }
        if (event === "result") {
          const parsed = JSON.parse(data);
          finalBotMessage = parsed.new_message;
        }
      }
    };

    while (true) {
      const { done, value } = await reader!.read();
      if (done) break;
      processChunk(decoder.decode(value));
    }

    setCurrentChat({
      ...currentChat,
      allMessages: currentChat.allMessages.map((msg: any) =>
        msg.id === messageId
          ? { ...msg, botMessage: finalBotMessage, isRetrying: false }
          : msg
      ),
    });
  } catch (err) {
    console.error(err);
    setCurrentChat({
      ...currentChat,
      allMessages: currentChat.allMessages.map((msg: any) =>
        msg.id === messageId ? { ...msg, isRetrying: false } : msg
      ),
    });
  }
};

export const handlePromptEdit = async (
  chatId: string,
  editedText: string,
  messageId: string,
  user: { token: string } | null,
  setCurrentChat: (chat: any) => void
) => {
  if (!editedText || !user) return;

  try {
    const res = await newMessageHandler(chatId || "", editedText, user.token, (evt: ChatSSEEvent) => {
      if (!evt) return;
      if (evt.label) {
        setCurrentChat((prevChat: any) => ({
          ...prevChat,
          allMessages: prevChat.allMessages.map((m: any) =>
            m.id === messageId ? { ...m, botMessage: evt.label } : m
          ),
        }));
      }
    });

    setCurrentChat((prevChat: any) => ({
      ...prevChat,
      allMessages: prevChat.allMessages.map((m: any) =>
        m.id === messageId ? { ...m, botMessage: res.new_message } : m
      ),
    }));
  } catch (err) {
    console.error("Error updating message:", err);
  }
};

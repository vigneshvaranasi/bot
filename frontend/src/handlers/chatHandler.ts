import { BE_URL } from "../config/config";
import { logger } from "../utils/logger";

export interface ChatSSEEventData {
  chunk?: string;
  message?: string;
  chat_id?: string;
  [key: string]: unknown;
}

export type ChatSSEEvent = { event: string; data: ChatSSEEventData; label?: string };

export const newMessageHandlerNoStream = async (
  chatId: string | null,
  prompt: string,
  token: string
) => {
  const headers = new Headers();
  headers.append("Authorization", `Bearer ${token}`);
  headers.append("Content-Type", "application/json");
  const response = await fetch(`${BE_URL}/chats/prompt`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      "chat_id": chatId,
      "message": prompt
    }),
  });

  if (!response.ok) {
    throw new Error("Failed to send message");
  }
  const data = await response.json();
  return data;
};


export const newMessageHandler = async (
  chatId: string | null,
  prompt: string,
  token: string,
  onEvent?: (evt: ChatSSEEvent) => void
) => {
  const headers = new Headers();
  headers.append("Authorization", `Bearer ${token}`);
  headers.append("Content-Type", "application/json");
  const response = await fetch(`${BE_URL}/chats/prompt/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      "chat_id": chatId,
      "message": prompt
    }),
  });

  if (!response.ok) {
    throw new Error("Failed to send message");
  }

  const contentType = response.headers.get("content-type");
  if (contentType && contentType.includes("application/json")) {
    const data = await response.json();
    if (data.success === false) {
      throw new Error(data.message || "Request failed");
    }
    return data;
  }

  let currChatId="";

  const reader = response.body?.getReader();

  if (!reader) {
    throw new Error("Failed to get reader");
  }

  const decoder = new TextDecoder("utf-8");
  let done = false;

  while (!done) {
    const { value, done: readerDone } = await reader.read();
    done = readerDone;

    if (value) {
      const chunk = decoder.decode(value, { stream: !done });
      const streamMessages = chunk.split("\n\n").filter(Boolean);

      for (const streamItem of streamMessages) {
        try {
          const [event, data] = streamItem.split("\n");
          const actualEvent = event.slice(6).trim();
          const parsedData = JSON.parse(data.slice(5).trim());
          if(onEvent){  
              onEvent({
                event: actualEvent,
                data: parsedData,
              });
          }
          if(actualEvent==="complete"){
            currChatId=parsedData.chat_id;
          }

          
        } catch (error) {
          logger.error("Error parsing SSE event:", error);
        }
      }
    }
  }
  return {
    chat_id: currChatId
  }
};

export const getAllMyChats = async (token: string) => {
  const headers = new Headers();
  headers.append("Authorization", `Bearer ${token}`);
  headers.append("Content-Type", "application/json");

  const response = await fetch(`${BE_URL}/chats/`, {
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

export const archiveChatById = async (token: string, chatId: string) => {
  const headers = new Headers();
  headers.append("Authorization", `Bearer ${token}`);
  headers.append("Content-Type", "application/json");
  
  const response = await fetch(`${BE_URL}/chats/archive/${chatId}`, {
    method: "DELETE",
    headers,
  });
  if (!response.ok) {
    throw new Error("Failed to archive chat");
  }
  const data = await response.json();
  return data;
};

export const renameChatById = async (token: string, chatId: string, title: string) => {
  const headers = new Headers();
  headers.append("Authorization", `Bearer ${token}`);
  headers.append("Content-Type", "application/json");
  
  const response = await fetch(`${BE_URL}/chats/rename/${chatId}`, {
    method: "PUT",
    headers,
    body: JSON.stringify({ title }),
  });
  if (!response.ok) {
    throw new Error("Failed to rename chat");
  }
  const data = await response.json();
  return data;
}
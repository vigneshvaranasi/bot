import { BE_URL } from "../config/config";

export const newMessageHandler = async (
  chatId: string | null,
  prompt: string,
  token: string
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
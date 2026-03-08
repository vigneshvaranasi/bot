export type ResponseMetrics = {
  timeToFirstChunk?: number;
  timeToFirstToken?: number;
  totalResponseTime: number;
  modelId?: string | null;
  providerType?: string | null;
};

// Display helper for durations: ms (<1s), s (<60s), min+sec (>=60s)
export const formatDuration = (ms: number) => {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(3)}s`;
  const minutes = Math.floor(ms / 60_000);
  const seconds = ((ms % 60_000) / 1000).toFixed(3);
  return `${minutes}min ${seconds}s`;
};

const keyForChat = (chatId: string) => `chat_metrics:${chatId}`;

export const saveChatMetrics = (chatId: string, metrics: ResponseMetrics) => {
  try {
    sessionStorage.setItem(keyForChat(chatId), JSON.stringify(metrics));
  } catch {
    // Session storage errors are non-critical
  }
};

export const readChatMetrics = (chatId: string): ResponseMetrics | null => {
  try {
    const raw = sessionStorage.getItem(keyForChat(chatId));
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
};

export const removeChatMetrics = (chatId: string) => {
  try {
    sessionStorage.removeItem(keyForChat(chatId));
  } catch {
    // Session storage errors are non-critical
  }
};

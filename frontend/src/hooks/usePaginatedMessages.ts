import { useState, useCallback, useRef } from "react";
import { getChatMessagesById, type PaginatedMessagesResponse } from "../handlers/chatHandler";
import type { ChatMessage } from "../types";
import { logger } from "../utils/logger";

const MESSAGES_PAGE_SIZE = 50;

export interface UsePaginatedMessagesOptions {
  /** Chat ID to fetch messages for */
  chatId: string;
  /** Current messages already in state */
  currentMessages: ChatMessage[];
  /** Callback to update messages state */
  onMessagesLoaded: (messages: ChatMessage[], hasMore: boolean, total: number) => void;
  /** User key for cache operations */
  userKey?: string;
}

export interface UsePaginatedMessagesReturn {
  /** Load older messages (for scroll-up pagination) */
  loadOlderMessages: () => Promise<void>;
  /** Whether there are older messages to load */
  hasOlderMessages: boolean;
  /** Whether currently loading older messages */
  isLoadingOlder: boolean;
  /** Error from last load attempt */
  error: Error | null;
  /** Clear error state */
  clearError: () => void;
  /** Pagination offset (how many messages loaded from start) */
  offset: number;
  /** Total messages available */
  total: number;
}

/**
 * Hook for paginated message loading with scroll position preservation support.
 * Loads older messages when scrolling up (reverse pagination).
 */
export function usePaginatedMessages({
  chatId,
  currentMessages,
  onMessagesLoaded,
}: UsePaginatedMessagesOptions): UsePaginatedMessagesReturn {
  const [isLoadingOlder, setIsLoadingOlder] = useState(false);
  const [hasOlderMessages, setHasOlderMessages] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);

  // Prevent concurrent loads
  const loadingRef = useRef(false);

  const loadOlderMessages = useCallback(async () => {
    if (loadingRef.current || isLoadingOlder || !hasOlderMessages || !chatId) {
      return;
    }

    loadingRef.current = true;
    setIsLoadingOlder(true);
    setError(null);

    try {
      const token = localStorage.getItem("token");
      if (!token) {
        throw new Error("Authentication required");
      }

      // Calculate the offset for older messages
      // We're loading messages BEFORE the current oldest message
      const newOffset = currentMessages.length;

      const response: PaginatedMessagesResponse = await getChatMessagesById(
        token,
        chatId,
        MESSAGES_PAGE_SIZE,
        newOffset
      );

      if (response && Array.isArray(response.messages)) {
        // Transform API messages to ChatMessage format
        const olderMessages: ChatMessage[] = response.messages.map((message) => ({
          id: message.id,
          userMessage: message.human || "",
          botMessage: message.bot || "",
        }));

        // Prepend older messages to existing messages
        const mergedMessages = [...olderMessages, ...currentMessages];

        // Update state
        setOffset(newOffset + olderMessages.length);
        setTotal(response.total);
        setHasOlderMessages(response.has_more);

        // Notify parent with merged messages
        onMessagesLoaded(mergedMessages, response.has_more, response.total);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err : new Error("Failed to load older messages");
      logger.error("Failed to load older messages:", err);
      setError(errorMessage);
    } finally {
      setIsLoadingOlder(false);
      loadingRef.current = false;
    }
  }, [chatId, currentMessages, hasOlderMessages, isLoadingOlder, onMessagesLoaded]);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // Expose a method to initialize pagination state from initial load
  const initializePagination = useCallback((hasMore: boolean, totalCount: number, initialOffset: number) => {
    setHasOlderMessages(hasMore);
    setTotal(totalCount);
    setOffset(initialOffset);
  }, []);

  return {
    loadOlderMessages,
    hasOlderMessages,
    isLoadingOlder,
    error,
    clearError,
    offset,
    total,
    // Expose initialization for use by parent component
    // @ts-expect-error - exposed for parent initialization
    initializePagination,
  };
}

/**
 * Utility function to capture scroll position before loading content.
 * Returns a restore function to call after DOM update.
 */
export function captureScrollPosition(
  containerRef: React.RefObject<HTMLDivElement>
): () => void {
  const container = containerRef.current;
  if (!container) {
    return () => {};
  }

  const prevScrollHeight = container.scrollHeight;
  const prevScrollTop = container.scrollTop;

  return () => {
    // Execute after DOM update
    requestAnimationFrame(() => {
      const newScrollHeight = container.scrollHeight;
      const heightDiff = newScrollHeight - prevScrollHeight;
      container.scrollTop = prevScrollTop + heightDiff;
    });
  };
}

export default usePaginatedMessages;

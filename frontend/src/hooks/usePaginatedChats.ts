import { useCallback, useRef } from "react";
import { getAllMyChats } from "../handlers/chatHandler";
import type { ChatInSidebar } from "../types";
import { logger } from "../utils/logger";

const CHATS_PAGE_SIZE = 20;

export interface UsePaginatedChatsOptions {
  /** Current chats in state */
  currentChats: ChatInSidebar[];
  /** Whether there are more chats to load */
  hasMore: boolean;
  /** Whether currently loading more chats */
  isLoadingMore: boolean;
  /** Set loading state */
  setIsLoadingMore: (loading: boolean) => void;
  /** Append new chats to existing list */
  appendChats: (newChats: ChatInSidebar[], hasMore: boolean, total: number) => void;
}

export interface UsePaginatedChatsReturn {
  /** Load more chats (for scroll-down pagination) */
  loadMoreChats: () => Promise<void>;
}

/**
 * Hook for paginated chat list loading in the sidebar.
 * Loads more chats when scrolling down (standard pagination).
 */
export function usePaginatedChats({
  currentChats,
  hasMore,
  isLoadingMore,
  setIsLoadingMore,
  appendChats,
}: UsePaginatedChatsOptions): UsePaginatedChatsReturn {
  // Prevent concurrent loads
  const loadingRef = useRef(false);

  const loadMoreChats = useCallback(async () => {
    if (loadingRef.current || isLoadingMore || !hasMore) {
      return;
    }

    loadingRef.current = true;
    setIsLoadingMore(true);

    try {
      const token = localStorage.getItem("token");
      if (!token) {
        throw new Error("Authentication required");
      }

      const offset = currentChats.length;
      const response = await getAllMyChats(token, CHATS_PAGE_SIZE, offset);

      if (response && Array.isArray(response.chats)) {
        const newChats: ChatInSidebar[] = response.chats.map(
          (chat: { id: string; title: string; updated_at: string }) => ({
            chatId: chat.id,
            chatTitle: chat.title,
            date: chat.updated_at,
          })
        );

        appendChats(newChats, response.has_more, response.total);
      }
    } catch (err) {
      logger.error("Failed to load more chats:", err);
    } finally {
      setIsLoadingMore(false);
      loadingRef.current = false;
    }
  }, [currentChats.length, hasMore, isLoadingMore, setIsLoadingMore, appendChats]);

  return {
    loadMoreChats,
  };
}

export default usePaginatedChats;

import { createContext, useState, useCallback, type ReactNode } from "react";
import type { ChatInSidebar } from "../types/Chats";
import type { ChatMessage } from "../types";

export type CurrentChatType = {
  chatId: string;
  allMessages: ChatMessage[];
  /** Whether there are older messages to load */
  hasOlderMessages?: boolean;
  /** Total messages count from API */
  totalMessages?: number;
};

/** Pagination state for sidebar chats */
export type ChatsPaginationState = {
  hasMore: boolean;
  total: number;
  offset: number;
  isLoadingMore: boolean;
};

type SidebarContextType = {
  isSidebarOpen: boolean;
  setSidebarOpen: React.Dispatch<React.SetStateAction<boolean>>;
  chats: ChatInSidebar[];
  setChats: React.Dispatch<React.SetStateAction<ChatInSidebar[]>>;
  currentChat: CurrentChatType | null;
  setCurrentChat: React.Dispatch<React.SetStateAction<CurrentChatType | null>>;
  toggleSidebar: () => void;
  isSidebarLoading: boolean;
  setIsSidebarLoading: React.Dispatch<React.SetStateAction<boolean>>;
  refreshChatsTick: number;
  triggerRefreshChats: () => void;
  /** Pagination state for sidebar chats */
  chatsPagination: ChatsPaginationState;
  /** Set pagination state */
  setChatsPagination: React.Dispatch<React.SetStateAction<ChatsPaginationState>>;
  /** Append chats for infinite scroll */
  appendChats: (newChats: ChatInSidebar[], hasMore: boolean, total: number) => void;
  /** Set loading more state */
  setIsLoadingMoreChats: (loading: boolean) => void;
};

const initialPaginationState: ChatsPaginationState = {
  hasMore: false,
  total: 0,
  offset: 0,
  isLoadingMore: false,
};

export const SidebarContext = createContext<SidebarContextType>({
  isSidebarOpen: false,
  setSidebarOpen: () => {},
  chats: [],
  setChats: () => {},
  currentChat: null,
  setCurrentChat: () => {},
  toggleSidebar: () => {},
  isSidebarLoading: false,
  setIsSidebarLoading: () => {},
  refreshChatsTick: 0,
  triggerRefreshChats: () => {},
  chatsPagination: initialPaginationState,
  setChatsPagination: () => {},
  appendChats: () => {},
  setIsLoadingMoreChats: () => {},
});

export const SidebarProvider = ({
  children,
}: {
  children: ReactNode;
}) => {
  const [isSidebarOpen, setSidebarOpen] = useState<boolean>(localStorage.getItem("isSidebarOpen") === "true" || false);
  const [chats, setChats] = useState<ChatInSidebar[]>([]);
  const [currentChat, setCurrentChat] = useState<CurrentChatType | null>(null);
  const [isSidebarLoading, setIsSidebarLoading] = useState<boolean>(false);
  const [refreshChatsTick, setRefreshChatsTick] = useState<number>(0);
  const [chatsPagination, setChatsPagination] = useState<ChatsPaginationState>(initialPaginationState);

  const toggleSidebar = () => {
    setSidebarOpen((prev) => {
      const next = !prev;
      localStorage.setItem("isSidebarOpen", JSON.stringify(next));
      return next;
    });
  };

  const triggerRefreshChats = () => {
    setRefreshChatsTick((prev) => prev + 1);
  };

  const appendChats = useCallback((newChats: ChatInSidebar[], hasMore: boolean, total: number) => {
    setChats((prev) => [...prev, ...newChats]);
    setChatsPagination((prev) => ({
      ...prev,
      hasMore,
      total,
      offset: prev.offset + newChats.length,
    }));
  }, []);

  const setIsLoadingMoreChats = useCallback((loading: boolean) => {
    setChatsPagination((prev) => ({
      ...prev,
      isLoadingMore: loading,
    }));
  }, []);

  return (
    <SidebarContext.Provider
      value={{
        isSidebarOpen,
        setSidebarOpen,
        chats,
        setChats,
        currentChat,
        setCurrentChat,
        toggleSidebar,
        isSidebarLoading,
        setIsSidebarLoading,
        refreshChatsTick,
        triggerRefreshChats,
        chatsPagination,
        setChatsPagination,
        appendChats,
        setIsLoadingMoreChats,
      }}
    >
      {children}
    </SidebarContext.Provider>
  );
};

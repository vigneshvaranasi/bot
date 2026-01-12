import { createContext, useState, type ReactNode } from "react";
import type { ChatInSidebar } from "../types/Chats";
import type { ChatMessage } from "../types";

export type CurrentChatType = {
  chatId: string;
  allMessages: ChatMessage[];
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
  triggerRefreshChats: () => {}
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

  const toggleSidebar = () => {
    setSidebarOpen((prev) => !prev);
    localStorage.setItem("isSidebarOpen", JSON.stringify(!isSidebarOpen));
  };

  const triggerRefreshChats = () => {
    setRefreshChatsTick((prev) => prev + 1);
  }

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
        triggerRefreshChats
      }}
    >
      {children}
    </SidebarContext.Provider>
  );
};

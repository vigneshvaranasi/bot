import { createContext, useState } from "react";
import type { ChatInSidebar } from "../types/Chats";

type currentChatType = {
  chatId: string | null;
  allMessages: {
    id: string;
    userMessage: string;
    botMessage: string;
  }[];
};

type SidebarContextType = {
  isSidebarOpen: boolean;
  setSidebarOpen: React.Dispatch<React.SetStateAction<boolean>>;
  chats: ChatInSidebar[];
  setChats: React.Dispatch<React.SetStateAction<ChatInSidebar[]>>;
  currentChat: currentChatType | null;
  setCurrentChat: React.Dispatch<React.SetStateAction<currentChatType | null>>;
  toggleSidebar: () => void;
};

export const SidebarContext = createContext<SidebarContextType>({
  isSidebarOpen: false,
  setSidebarOpen: () => {},
  chats: [],
  setChats: () => {},
  currentChat: null,
  setCurrentChat: () => {},
  toggleSidebar: () => {},

});

export const SidebarProvider = ({
  children,
}: {
  children: React.ReactNode;
}) => {
  const [isSidebarOpen, setSidebarOpen] = useState<boolean>(localStorage.getItem("isSidebarOpen") === "true" || false);
  const [chats, setChats] = useState<ChatInSidebar[]>([]);
  const [currentChat, setCurrentChat] = useState<currentChatType | null>(null);

  const closeSidebar = () => {
    setSidebarOpen(false);
    localStorage.setItem("isSidebarOpen", "false");
  };

  const openSidebar = () => {
    setSidebarOpen(true);
    localStorage.setItem("isSidebarOpen", "true");
  };

  const toggleSidebar = () => {
    setSidebarOpen((prev) => !prev);
    localStorage.setItem("isSidebarOpen", JSON.stringify(!isSidebarOpen));
  };

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
      }}
    >
      {children}
    </SidebarContext.Provider>
  );
};

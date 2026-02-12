import { useState } from "react";
import Navbar from "../components/Navbar";
import Sidebar from "../components/Sidebar";
import PromptBar from "../components/PromptBar";
import type { ModelOverride } from "../components/PromptBar";
import { useSidebarContext } from "../hooks/useSidebarContext";
import { Outlet, useNavigate, useParams } from "react-router-dom";
import { newMessageHandler } from "../handlers/chatHandler";
import { useAuthContext } from "../hooks/useAuthContext";
import { saveChatMetrics } from "../utils/metrics";
import { saveChatToCache } from "../utils/chatCache";
import { createMessageStreamer } from "../utils/streaming";
import { logger } from "../utils/logger";
import type { ChatMessage } from "../types";
import type { CurrentChatType } from "../store/SidebarContext";

function ChatPage() {
  const { isSidebarOpen, setCurrentChat, currentChat, triggerRefreshChats } =
    useSidebarContext();
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const { chatId } = useParams<{ chatId: string }>();
  const { user } = useAuthContext();
  const navigate = useNavigate();

  const handlePromptSendStream = async (prompt: string, modelOverride?: ModelOverride) => {
    if (!prompt || !user) {
      logger.error("Invalid prompt or user");
      return;
    }
    const newMessageId = Date.now().toString();

    try {
      const currChatId = chatId || "";
      logger.debug("currChatId:", currChatId);

      setCurrentChat((prevChat: CurrentChatType | null) => ({
        chatId: currChatId,
        allMessages: [
          ...(prevChat?.allMessages ?? []),
          {
            id: newMessageId,
            userMessage: prompt,
            botMessage: "",
            statusMessage: "Thinking...",
            streaming: true,
          },
        ],
      }));
      setIsLoading(true);

      // streamer
      const streamer = createMessageStreamer({
        setCurrentChat,
        messageId: newMessageId,
      });
      streamer.markStart();

      const token = localStorage.getItem("token");
      if (!token) {
        logger.error("Token missing");
        return;
      }

      const res = await newMessageHandler(
        currChatId,
        prompt,
        token,
        streamer.onEvent,
        modelOverride
      );
      const metrics = streamer.getMetrics();
      if (currChatId === "") {
        if (res?.chat_id) {
          saveChatMetrics(res.chat_id, metrics);
        }
        triggerRefreshChats();
        navigate(`/${res.chat_id}`);
        return;
      }

      try {
        const toCache = currentChat?.allMessages.map((m: ChatMessage) => ({
          id: m.id,
          userMessage: m.userMessage,
          botMessage: m.botMessage,
          responseMetrics: m.responseMetrics,
        }));
        await saveChatToCache(res.chat_id, toCache!, 20, user?.email);
      } catch {
        // Cache errors are non-critical
      }
    } catch (error: unknown) {
      logger.error("Error sending prompt:", error);
      const errorMessage = error instanceof Error ? error.message : "An error occurred.";
      setCurrentChat((prevChat: CurrentChatType | null) => {
        if (!prevChat) return null;
        const updatedMessages = prevChat.allMessages.map((msg: ChatMessage) => {
          if (msg.id === newMessageId) {
            return {
              ...msg,
              botMessage: errorMessage,
              streaming: false,
            };
          }
          return msg;
        });
        return {
          ...prevChat,
          allMessages: updatedMessages,
        };
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={`flex h-screen`}>
      <Sidebar />
      <div className={`flex-1 min-w-0 ${isSidebarOpen && "hidden md:block"}`}>
        <div className="flex flex-col h-screen">
          <Navbar />
          <div className="flex-1 min-h-0 overflow-y-auto">
            <Outlet />
          </div>
          <PromptBar onSend={handlePromptSendStream} isLoading={isLoading} />
        </div>
      </div>
    </div>
  );
}

export default ChatPage;

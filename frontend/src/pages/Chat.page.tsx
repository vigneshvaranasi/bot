import { useState, useRef } from "react";
import Navbar from "../components/Navbar";
import Sidebar from "../components/Sidebar";
import PromptBar from "../components/PromptBar";
import type { ModelOverride } from "../components/PromptBar";
import { useSidebarContext } from "../hooks/useSidebarContext";
import { Outlet, useNavigate, useParams } from "react-router-dom";
import { newMessageHandler, savePartialMessage } from "../handlers/chatHandler";
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
  const abortRef = useRef<AbortController | null>(null);
  const mergedMetricsRef = useRef<{ timeToFirstToken?: number; totalResponseTime: number; modelId?: string | null; providerType?: string | null } | null>(null);

  const handleStop = () => {
    abortRef.current?.abort();
    abortRef.current = null;
  };

  const handlePromptSendStream = async (prompt: string, modelOverride?: ModelOverride) => {
    if (!prompt || !user) {
      logger.error("Invalid prompt or user");
      return;
    }
    const newMessageId = Date.now().toString();
    const currChatId = chatId || "";
    const controller = new AbortController();
    abortRef.current = controller;

    let streamedChatId = "";
    let streamedMessageId = "";

    try {
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
            sentAt: new Date().toISOString(),
          },
        ],
      }));
      setIsLoading(true);

      // streamer
      mergedMetricsRef.current = null;
      const streamer = createMessageStreamer({
        setCurrentChat,
        messageId: newMessageId,
        onComplete: (m) => {
          mergedMetricsRef.current = m;
        },
      });
      streamer.markStart();

      const token = localStorage.getItem("token");
      if (!token) {
        logger.error("Token missing");
        return;
      }

      const wrappedOnEvent = (evt: Parameters<typeof streamer.onEvent>[0]) => {
        if (evt?.data?.chat_id) {
          streamedChatId = evt.data.chat_id as string;
        }
        if (evt?.data?.message_id) {
          streamedMessageId = evt.data.message_id as string;
        }
        streamer.onEvent(evt);
      };

      const res = await newMessageHandler(
        currChatId,
        prompt,
        token,
        wrappedOnEvent,
        modelOverride,
        controller.signal
      );
      const metrics = mergedMetricsRef.current ?? streamer.getMetrics();
      if (currChatId === "") {
        if (res?.chat_id) {
          saveChatMetrics(res.chat_id, metrics);
          triggerRefreshChats();
          navigate(`/${res.chat_id}`);
        } else {
          triggerRefreshChats();
        }
        return;
      }

      try {
        const toCache = currentChat?.allMessages.map((m: ChatMessage) => ({
          id: m.id,
          userMessage: m.userMessage,
          botMessage: m.botMessage,
          responseMetrics: m.responseMetrics,
        }));
        if (res?.chat_id) {
          await saveChatToCache(res.chat_id, toCache!, 20, user?.email);
        }
      } catch {
        // Cache errors are non-critical
      }
    } catch (error: unknown) {
      if (controller.signal.aborted) {
        let partialBot = "";
        setCurrentChat((prevChat: CurrentChatType | null) => {
          if (!prevChat) return null;
          const updatedMessages = prevChat.allMessages.map((msg: ChatMessage) => {
            if (msg.id === newMessageId) {
              partialBot = msg.botMessage || "";
              return {
                ...msg,
                streaming: false,
                stopped: true,
                statusMessage: undefined,
              };
            }
            return msg;
          });
          return {
            ...prevChat,
            chatId: streamedChatId || prevChat.chatId,
            allMessages: updatedMessages,
          };
        });

        if (currChatId === "" && streamedChatId) {
          navigate(`/${streamedChatId}`, { replace: true });
          triggerRefreshChats();
        }

        if (streamedMessageId && partialBot) {
          const token = localStorage.getItem("token");
          if (token) {
            savePartialMessage(token, streamedMessageId, partialBot);
          }
        }
      } else {
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
          return { ...prevChat, allMessages: updatedMessages };
        });
      }
    } finally {
      abortRef.current = null;
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
          <PromptBar
            onSend={handlePromptSendStream}
            onStop={handleStop}
            isLoading={isLoading}
            canStop={isLoading && (currentChat?.allMessages.some((m: ChatMessage) => m.streaming) ?? false)}
          />
        </div>
      </div>
    </div>
  );
}

export default ChatPage;

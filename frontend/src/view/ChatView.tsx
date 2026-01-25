import Bubble from "../components/ui/Bubble";
import { useParams } from "react-router-dom";
import { useAuthContext } from "../hooks/useAuthContext";
import { useEffect, useLayoutEffect, useState, useRef, useCallback } from "react";
import { getChatMessagesById } from "../handlers/chatHandler";
import { readChatMetrics, removeChatMetrics } from "../utils/metrics";
import { useSidebarContext } from "../hooks/useSidebarContext";
import { useSpeechSynthesis } from "../hooks/useSpeechSynthesis";
import { loadChatFromCache, saveChatToCache, messagesEqual } from "../utils/chatCache";
import { ChatAction } from "../components/ui/ChatAction";
import { logger } from "../utils/logger";
import type { ChatMessage } from "../types";
import { SkeletonChatConversation } from "../components/ui/Skeleton";
import { useDelayedLoading } from "../hooks/useDelayedLoading";

// API response message structure from getChatMessagesById
interface ApiChatMessage {
  id: string;
  human: string;
  bot: string;
}

const ChatView = () => {
  const { chatId } = useParams<{ chatId: string }>();
  const { user } = useAuthContext();
  const { currentChat, setCurrentChat } = useSidebarContext();
  const { speak, stop, isSpeaking } = useSpeechSynthesis();
  const [speakingMessageId, setSpeakingMessageId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Delayed loading - only show skeleton after 150ms
  const showLoading = useDelayedLoading(loading);

  const bottomRef = useRef<HTMLDivElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const scrollToBottom = useCallback((smooth: boolean = true) => {
    const container = containerRef.current;
    if (!container) return;
    if (bottomRef.current) {
      try {
        bottomRef.current.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "end" });
      } catch {
        // scrollIntoView may fail in some edge cases - fallback to scrollTop below
      }
    }
    container.scrollTop = container.scrollHeight;
  }, []);

  useEffect(() => {
    if (!user || !chatId) return;
    setLoading(true);

    const fetchMessages = async () => {
      try {
        const userKey = user?.email;
        // Try IndexedDB cache
        const cached = await loadChatFromCache(chatId, userKey);
        if (cached && Array.isArray(cached)) {
          setCurrentChat({ chatId, allMessages: cached as ChatMessage[] });
          setLoading(false);
        }

        // Always fetch from server in the bg
        const token = localStorage.getItem("token");
        if (!token) return;
        const res = await getChatMessagesById(token, chatId);
        let freshMessages: ChatMessage[] = [];
        // Handle new paginated response format - messages are in res.messages
        const messageData = res && res.messages ? res.messages : res;
        if (messageData && Array.isArray(messageData)) {
          freshMessages = (messageData as ApiChatMessage[]).map((message: ApiChatMessage) => ({
            id: message.id,
            userMessage: message.human || "",
            botMessage: message.bot || "",
          }));
          // get and attach metrics to the last message
          const metrics = readChatMetrics(chatId);
          if (metrics && freshMessages.length > 0) {
            const lastIdx = freshMessages.length - 1;
            freshMessages[lastIdx] = {
              ...freshMessages[lastIdx],
              responseMetrics: metrics,
            };
            removeChatMetrics(chatId);
          }
        }

        // Update UI only if changed vs cached
        const curr = (cached as ChatMessage[]) || [];
        if (!messagesEqual(curr, freshMessages)) {
          setCurrentChat({ chatId, allMessages: freshMessages });
        }
        // Save refreshed messages to cache
        await saveChatToCache(chatId, freshMessages, 20, userKey);
      } catch (err) {
        logger.error("Failed to fetch messages:", err);
        setCurrentChat({
          chatId: chatId,
          allMessages: [],
        });
      } finally {
        setLoading(false);
      }
    };

    fetchMessages();

    return () => {
      setCurrentChat(null);
    };
  }, [chatId, user]);

  useLayoutEffect(() => {
    scrollToBottom(false);
  }, [chatId, scrollToBottom]);

  // Scroll when number of messages changes
  useEffect(() => {
    requestAnimationFrame(() => scrollToBottom());
    const t1 = setTimeout(() => scrollToBottom(), 40);
    const t2 = setTimeout(() => scrollToBottom(false), 120);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [currentChat?.allMessages?.length, loading, scrollToBottom]);

  const handleSpeechToggle = useCallback((messageId: string, content: string) => {
    if (isSpeaking && speakingMessageId === messageId) {
      stop();
      setSpeakingMessageId(null);
    } 
    else {
      stop();
      setSpeakingMessageId(messageId);
      speak(content);
    }
  }, [isSpeaking, speakingMessageId, speak, stop]);

  useEffect(() => {
    return () => {
      stop();
      setSpeakingMessageId(null);
    };
  }, [chatId, stop]);

  useEffect(() => {
    if (!isSpeaking) {
      setSpeakingMessageId(null);
    }
  }, [isSpeaking]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    if (typeof ResizeObserver !== "undefined") {
      const ro = new ResizeObserver(() => scrollToBottom(false));
      ro.observe(el);
      return () => ro.disconnect();
    }
  }, [scrollToBottom]);

  if (!user) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-lg md:text-2xl">Please login to view the chat</p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="flex-1 space-y-4 px-3" style={{ WebkitOverflowScrolling: "touch" }}>
        {showLoading && !currentChat?.allMessages?.length ? (
          <div className="py-6 px-2">
            <SkeletonChatConversation messages={2} />
          </div>
        ) : currentChat?.allMessages.length === 0 ? (
          <p>No messages found</p>
        ) : (
          currentChat?.allMessages.map((message) => (
          <div key={message.id}>
            <Bubble variant="user" content={message.userMessage} />
            <Bubble
              variant="bot"
              content={message.botMessage}
              streaming={message.streaming}
              statusMessage={message.statusMessage}
            />
            {/* chat Actions */}
            {
              !message.streaming &&
              <div className="flex items-center gap-0.5 ml-2">
                {/* <ChatAction type="retry"/>
                <ChatAction type="thumbsUp"/>
                <ChatAction type="thumbsDown"/> */}
                <ChatAction type="copy" content={message.botMessage}/>
                <ChatAction 
                  type="speaker" 
                  content={message.botMessage}
                  isSpeaking={isSpeaking && speakingMessageId === message.id}
                  onSpeakToggle={() => handleSpeechToggle(message.id, message.botMessage)}
                />
                {
                  message.responseMetrics && 
                  <ChatAction type="metrics" responseMetrics={message.responseMetrics}/>
                }
            </div>
            }
          </div>
        ))
      )}
      <div ref={bottomRef} data-bottom-marker />
      {
        chatId == undefined && currentChat == null && (
          <div className="flex items-center justify-center h-full py-10">
            <p className="text-lg md:text-2xl">
              How can I help you today?
            </p>
          </div>
        )
      }
      </div>
  );
};

export default ChatView;

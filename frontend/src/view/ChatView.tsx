import Bubble from "../components/ui/Bubble";
import { useParams } from "react-router-dom";
import { useAuthContext } from "../hooks/useAuthContext";
import { useEffect, useLayoutEffect, useState, useRef, useCallback } from "react";
import { getChatMessagesById } from "../handlers/chatHandler";
import { readChatMetrics, removeChatMetrics } from "../utils/metrics";
import { useSidebarContext } from "../hooks/useSidebarContext";
import Spinner from "../components/ui/Spinner";
import { loadChatFromCache, saveChatToCache, messagesEqual } from "../utils/chatCache";

const ChatView = () => {
  const { chatId } = useParams<{ chatId: string }>();
  const { user } = useAuthContext();
  const { currentChat, setCurrentChat } = useSidebarContext();
  const [loading, setLoading] = useState(false);

  const bottomRef = useRef<HTMLDivElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const scrollToBottom = useCallback((smooth: boolean = true) => {
    const container = containerRef.current;
    if (!container) return;
    if (bottomRef.current) {
      try {
        bottomRef.current.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "end" });
      } catch {
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
          setCurrentChat({ chatId, allMessages: cached as any });
          setLoading(false);
        }

        // Always fetch from server in the bg
        const res = await getChatMessagesById(user?.token, chatId);
        let freshMessages: any[] = [];
        if (res && Array.isArray(res)) {
          freshMessages = res.map((message: any) => ({
            id: message.id,
            userMessage: message.user_query || "",
            botMessage: message.bot_solution || "",
          }));
          // get and attach metrics to the last message
          const metrics = readChatMetrics(chatId);
          if (metrics && freshMessages.length > 0) {
            const lastIdx = freshMessages.length - 1;
            freshMessages[lastIdx] = {
              ...freshMessages[lastIdx],
              responseMetrics: metrics,
            } as any;
            removeChatMetrics(chatId);
          }
        }

        // Update UI only if changed vs cached
        const curr = cached || [];
        if (!messagesEqual(curr as any, freshMessages as any)) {
          setCurrentChat({ chatId, allMessages: freshMessages as any });
        }
        // Save refreshed messages to cache
        await saveChatToCache(chatId, freshMessages as any, 20, userKey);
      } catch (err) {
        console.error("Failed to fetch messages:", err);
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
    <div ref={containerRef} className="flex-1 space-y-4 overflow-y-auto px-3" style={{ WebkitOverflowScrolling: "touch" }}>
      {loading ? (
        <div className="flex items-center justify-center h-full py-10">
          <Spinner size={20} />
        </div>
      ) : currentChat?.allMessages.length === 0 ? (
        <p>No messages found</p>
      ) : (
        currentChat?.allMessages.map((message) => (
          <div key={message.id}>
            <Bubble variant="user" content={message.userMessage} />
            <Bubble variant="bot" content={message.botMessage} streaming={message.streaming} />
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

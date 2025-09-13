import { useEffect, useLayoutEffect, useState, useRef, useCallback } from "react";
import { useParams } from "react-router-dom";
import Bubble from "../components/ui/Bubble";
import Spinner from "../components/ui/Spinner";
import { ChatActionButton } from "../components/ui/ChatActionButton";
import editIcon from "../assets/edit.svg";

import { useAuthContext } from "../hooks/useAuthContext";
import { useSidebarContext } from "../hooks/useSidebarContext";
import { getChatMessagesById,handleRetry, handlePromptEdit } from "../handlers/chatHandler";


const ChatView = () => {
  const { chatId } = useParams<{ chatId: string }>();
  const { user } = useAuthContext();
  const { currentChat, setCurrentChat } = useSidebarContext();

  const [loading, setLoading] = useState(false);
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");

  const containerRef = useRef<HTMLDivElement | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const scrollToBottom = useCallback((smooth: boolean = true) => {
    const container = containerRef.current;
    if (!container) return;
    if (bottomRef.current) {
      try {
        bottomRef.current.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "end" });
      } catch {}
    }
    container.scrollTop = container.scrollHeight;
  }, []);

   // Scroll when number of messages changes
  useEffect(() => {
    if (!user || !chatId) return;
    setLoading(true);

    const fetchMessages = async () => {
      try {
        const res = await getChatMessagesById(user.token, chatId);
        if (res && Array.isArray(res)) {
          const messages = res.map((message: any) => ({
            id: message.id,
            userMessage: message.user_query || "",
            botMessage: message.bot_solution || "",
          }));
          setCurrentChat({ chatId, allMessages: messages });
        } else {
          setCurrentChat({ chatId, allMessages: [] });
        }
      } catch (err) {
        console.error("Failed to fetch messages:", err);
        setCurrentChat({ chatId, allMessages: [] });
      } finally {
        setLoading(false);
      }
    };

    fetchMessages();
    return () => setCurrentChat(null);
  }, [chatId, user, setCurrentChat]);

  useLayoutEffect(() => {
    scrollToBottom(false);
  }, [chatId, scrollToBottom]);

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
    <div
      ref={containerRef}
      className="flex-1 space-y-4 overflow-y-auto px-3"
      style={{ WebkitOverflowScrolling: "touch" }}
    >
      {loading ? (
        <div className="flex items-center justify-center h-full py-10">
          <Spinner size={20} />
        </div>
      ) : currentChat?.allMessages.length === 0 ? (
        <p>No messages found</p>
      ) : (
        currentChat?.allMessages.map((message: any) => (
          <div key={message.id} className="relative">
            {editingMessageId === message.id ? (
              <div className="relative mt-1">
                <textarea
                  value={editText}
                  onChange={(e) => setEditText(e.target.value)}
                  className="w-full p-3 pr-24 rounded-xl border border-gray-300 bg-gray-200 focus:outline-none focus:border-gray-400 resize-none"
                  rows={4}
                  autoFocus
                />
                <div className="absolute bottom-2 right-2 flex gap-2">
                  <button
  onClick={() => {
    if (!editText.trim()) return;
    setEditingMessageId(null);
    setCurrentChat((prev: any) => ({
      ...prev,
      allMessages: prev.allMessages.map((m: any) =>
        m.id === message.id ? { ...m, userMessage: editText, botMessage: "Thinking..." } : m
      ),
    }));
    handlePromptEdit(chatId || "", editText, message.id, user, setCurrentChat);
    setEditText("");
  }}
  className="px-4 py-2 bg-black text-white rounded-full text-sm hover:bg-gray-800"
>
  Send
</button>

                  <button
                    onClick={() => {
                      setEditingMessageId(null);
                      setEditText("");
                    }}
                    className="px-4 py-2 bg-white text-black border border-gray-300 rounded-full text-sm hover:bg-gray-100"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <>
                <Bubble variant="user" content={message.userMessage} />
                <div className="flex justify-end mt-1">
                  <img
                    src={editIcon}
                    alt="Edit"
                    className="w-5 h-5 cursor-pointer hover:opacity-80"
                    onClick={() => {
                      setEditingMessageId(message.id);
                      setEditText(message.userMessage);
                    }}
                  />
                </div>
                <Bubble variant="bot" content={message.botMessage} />
                <div className="flex gap-2 mt-2">
                  <ChatActionButton
                    type="retry"
                    onClick={() =>
                      handleRetry(message.id, message.userMessage, user, currentChat, setCurrentChat)
                    }
                    loading={message.isRetrying}
                  />
                  <ChatActionButton type="thumbsUp" onClick={() => console.log("Thumbs up clicked")} />
                  <ChatActionButton type="thumbsDown" onClick={() => console.log("Thumbs down clicked")} />
                </div>
              </>
            )}
          </div>
        ))
      )}
      <div ref={bottomRef} data-bottom-marker />
      {chatId === undefined && currentChat === null && (
        <div className="flex items-center justify-center h-full py-10">
          <p className="text-lg md:text-2xl">How can I help you today?</p>
        </div>
      )}
    </div>
  );
};

export default ChatView;
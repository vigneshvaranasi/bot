import Bubble from "../components/ui/Bubble";
import { useParams } from "react-router-dom";
import { useAuthContext } from "../hooks/useAuthContext";
import { useEffect, useLayoutEffect, useState, useRef, useCallback } from "react";
import { getChatMessagesById, type PaginatedMessagesResponse } from "../handlers/chatHandler";
import { submitFeedback, getFeedbackForMessages } from "../handlers/feedbackHandler";
import { readChatMetrics, removeChatMetrics } from "../utils/metrics";
import { useSidebarContext } from "../hooks/useSidebarContext";
import { useSpeechSynthesis } from "../hooks/useSpeechSynthesis";
import { loadChatFromCache, saveChatToCache, mergeOlderMessages } from "../utils/chatCache";
import { ChatAction } from "../components/ui/ChatAction";
import { InlineFeedback } from "../components/ui/InlineFeedback";
import { logger } from "../utils/logger";
import type { ChatMessage, FeedbackType } from "../types";
import { SkeletonChatConversation } from "../components/ui/Skeleton";
import { useDelayedLoading } from "../hooks/useDelayedLoading";
import { toast } from "react-hot-toast";

// API response message structure from getChatMessagesById
interface ApiChatMessage {
  id: string;
  human: string;
  bot: string;
  created_at?: string | null;
  responded_at?: string | null;
  time_to_first_token_ms?: number | null;
  total_response_time_ms?: number | null;
  model_id?: string | null;
  provider_type?: string | null;
}

const MESSAGES_PAGE_SIZE = 50;

function formatMessageTime(iso: string | undefined | null): string {
  if (!iso) return "—";
  try {
    const utcIso = iso.endsWith("Z") || iso.includes("+") || iso.includes("-", 10) ? iso : iso + "Z";
    const d = new Date(utcIso);
    if (Number.isNaN(d.getTime())) return "—";
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}

const ChatView = () => {
  const { chatId } = useParams<{ chatId: string }>();
  const { user } = useAuthContext();
  const { currentChat, setCurrentChat } = useSidebarContext();
  const { speak, stop, isSpeaking } = useSpeechSynthesis();
  const [speakingMessageId, setSpeakingMessageId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [activeFeedback, setActiveFeedback] = useState<{
    messageId: string | null;
    feedbackType: FeedbackType;
  }>({ messageId: null, feedbackType: 'positive' });
  const [feedbackLoading, setFeedbackLoading] = useState(false);

  // Pagination state for infinite scroll
  const [hasOlderMessages, setHasOlderMessages] = useState(false);
  const [isLoadingOlder, setIsLoadingOlder] = useState(false);
  const loadingOlderRef = useRef(false);

  // Delayed loading - only show skeleton after 150ms
  const showLoading = useDelayedLoading(loading);

  const bottomRef = useRef<HTMLDivElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const contentRef = useRef<HTMLDivElement | null>(null);
  const topSentinelRef = useRef<HTMLDivElement | null>(null);

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
    // Reset pagination state for new chat
    setHasOlderMessages(false);

    const fetchMessages = async () => {
      try {
        const userKey = user?.email;
        // Try IndexedDB cache
        const cached = await loadChatFromCache(chatId, userKey);
        if (cached && cached.messages && Array.isArray(cached.messages)) {
          setCurrentChat({ chatId, allMessages: cached.messages as ChatMessage[] });
          // Restore pagination state from cache if available
          if (cached.pagination) {
            setHasOlderMessages(cached.pagination.hasMore);
          }
          setLoading(false);
        }

        // Always fetch from server in the bg
        const token = localStorage.getItem("token");
        if (!token) return;
        const res: PaginatedMessagesResponse = await getChatMessagesById(token, chatId, MESSAGES_PAGE_SIZE, 0);
        let freshMessages: ChatMessage[] = [];
        const messageData = res && res.messages ? res.messages : [];
        const success = res && res.error !== true && Array.isArray(messageData);

        if (success) {
          freshMessages = (messageData as ApiChatMessage[]).map((message: ApiChatMessage) => {
            const ttft = message.time_to_first_token_ms;
            const totalMs = message.total_response_time_ms;
            const modelId = message.model_id != null && String(message.model_id).trim() !== "" ? message.model_id : undefined;
            const providerType = message.provider_type != null && String(message.provider_type).trim() !== "" ? message.provider_type : undefined;
            const hasTiming = ttft != null && totalMs != null;
            const hasModelOrProvider = modelId != null || providerType != null;
            const hasAnyMetrics = hasTiming || hasModelOrProvider;

            return {
              id: message.id,
              userMessage: message.human || "",
              botMessage: message.bot || "",
              sentAt: message.created_at ?? undefined,
              respondedAt: message.responded_at ?? undefined,
              modelId: modelId ?? undefined,
              providerType: providerType ?? undefined,
              responseMetrics: hasAnyMetrics
                ? {
                    timeToFirstToken: ttft ?? undefined,
                    totalResponseTime: totalMs ?? 0,
                    modelId: modelId ?? undefined,
                    providerType: providerType ?? undefined,
                  }
                : undefined,
            };
          });

          const metrics = readChatMetrics(chatId);
          if (metrics && freshMessages.length > 0) {
            const lastIdx = freshMessages.length - 1;
            const last = freshMessages[lastIdx];
            if (!last.responseMetrics?.totalResponseTime) {
              freshMessages[lastIdx] = {
                ...last,
                responseMetrics: { ...last.responseMetrics, ...metrics },
              };
            }
            removeChatMetrics(chatId);
          }
        }

        setHasOlderMessages(success ? (res.has_more ?? false) : false);

        if (success) {
          setCurrentChat({ chatId, allMessages: freshMessages });
          await saveChatToCache(chatId, freshMessages, 20, userKey, {
            hasMore: res.has_more ?? false,
            total: res.total ?? freshMessages.length,
            offset: freshMessages.length,
          });
        }
      } catch (err) {
        logger.error("Failed to fetch messages:", err);
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

  const wasStreamingRef = useRef(false);
  useEffect(() => {
    const isStreaming = currentChat?.allMessages?.some(m => m.streaming) ?? false;
    if (wasStreamingRef.current && !isStreaming) {
      scrollToBottom(false);
      const t1 = setTimeout(() => scrollToBottom(false), 50);
      const t2 = setTimeout(() => scrollToBottom(false), 200);
      return () => { clearTimeout(t1); clearTimeout(t2); };
    }
    wasStreamingRef.current = isStreaming;
  }, [currentChat?.allMessages, scrollToBottom]);

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

  const handleFeedbackClick = useCallback((messageId: string, feedbackType: FeedbackType) => {
    const message = currentChat?.allMessages.find(m => m.id === messageId);
    if (message?.feedback === feedbackType) {
      return;
    }
    
    const isLastMessage = currentChat?.allMessages && 
      currentChat.allMessages.length > 0 && 
      currentChat.allMessages[currentChat.allMessages.length - 1].id === messageId;
    
    if (activeFeedback.messageId === messageId && activeFeedback.feedbackType === feedbackType) {
      setActiveFeedback({ messageId: null, feedbackType: 'positive' });
    } else {
      setActiveFeedback({ messageId, feedbackType });
      if (isLastMessage) {
        setTimeout(() => scrollToBottom(true), 50);
      }
    }
  }, [currentChat?.allMessages, activeFeedback.messageId, activeFeedback.feedbackType, scrollToBottom]);

  const handleFeedbackSubmit = useCallback(async (reason: string) => {
    const { messageId, feedbackType } = activeFeedback;
    if (!messageId) return;

    setFeedbackLoading(true);
    try {
      const token = localStorage.getItem("token");
      if (!token) throw new Error("Not authenticated");

      const response = await submitFeedback(token, messageId, feedbackType, reason);
      
      setCurrentChat((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          allMessages: prev.allMessages.map((m) =>
            m.id === messageId
              ? { ...m, feedback: feedbackType, feedbackId: response.id }
              : m
          ),
        };
      });

      toast.success(feedbackType === 'positive' ? 'Thanks for the feedback!' : 'Feedback submitted');

      setActiveFeedback({ messageId: null, feedbackType: 'positive' });
    } catch (err: any) {
      logger.error("Failed to submit feedback:", err);
      toast.error(err.message || 'Failed to submit feedback');
    } finally {
      setFeedbackLoading(false);
    }
  }, [activeFeedback, setCurrentChat]);

  const handleFeedbackCancel = useCallback(() => {
    setActiveFeedback({ messageId: null, feedbackType: 'positive' });
  }, []);

  useEffect(() => {
    const loadFeedback = async () => {
      if (!currentChat?.allMessages?.length) return;
      
      const token = localStorage.getItem("token");
      if (!token) return;

      const messageIds = currentChat.allMessages
        .filter(m => !m.streaming && !m.feedback)
        .map(m => m.id);
      
      if (messageIds.length === 0) return;

      try {
        const feedbackMap = await getFeedbackForMessages(token, messageIds);
        
        if (feedbackMap.size > 0) {
          setCurrentChat((prev) => {
            if (!prev) return prev;
            return {
              ...prev,
              allMessages: prev.allMessages.map((m) => {
                const feedback = feedbackMap.get(m.id);
                if (feedback) {
                  return {
                    ...m,
                    feedback: feedback.feedback_type,
                    feedbackId: feedback.id,
                  };
                }
                return m;
              }),
            };
          });
        }
      } catch (err) {
        logger.error("Failed to load feedback:", err);
      }
    };

    loadFeedback();
  }, [currentChat?.chatId, currentChat?.allMessages?.length, setCurrentChat]);

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
    const container = containerRef.current;
    const content = contentRef.current;
    if (!container || !content) return;
    if (typeof ResizeObserver !== "undefined") {
      const ro = new ResizeObserver(() => {
        const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 300;
        if (isNearBottom) {
          scrollToBottom(false);
        }
      });
      ro.observe(content);
      return () => ro.disconnect();
    }
  }, [scrollToBottom]);

  // Load older messages with scroll position preservation
  const loadOlderMessages = useCallback(async () => {
    if (loadingOlderRef.current || isLoadingOlder || !hasOlderMessages || !chatId) {
      return;
    }

    const container = containerRef.current;
    if (!container) return;

    // Capture scroll position before loading
    const prevScrollHeight = container.scrollHeight;
    const prevScrollTop = container.scrollTop;

    loadingOlderRef.current = true;
    setIsLoadingOlder(true);

    try {
      const token = localStorage.getItem("token");
      if (!token) return;

      const currentMessages = currentChat?.allMessages || [];
      const offset = currentMessages.length;

      const res: PaginatedMessagesResponse = await getChatMessagesById(
        token,
        chatId,
        MESSAGES_PAGE_SIZE,
        offset
      );

      if (res && Array.isArray(res.messages)) {
        const olderMessages: ChatMessage[] = res.messages.map((message) => {
          const ttft = message.time_to_first_token_ms;
          const totalMs = message.total_response_time_ms;
          const modelId = message.model_id != null && String(message.model_id).trim() !== "" ? message.model_id : undefined;
          const providerType = message.provider_type != null && String(message.provider_type).trim() !== "" ? message.provider_type : undefined;
          const hasAnyMetrics = ttft != null || totalMs != null || modelId != null || providerType != null;

          return {
            id: message.id,
            userMessage: message.human || "",
            botMessage: message.bot || "",
            sentAt: message.created_at ?? undefined,
            respondedAt: message.responded_at ?? undefined,
            modelId: modelId ?? undefined,
            providerType: providerType ?? undefined,
            responseMetrics: hasAnyMetrics
              ? {
                  timeToFirstToken: ttft ?? undefined,
                  totalResponseTime: totalMs ?? 0,
                  modelId: modelId ?? undefined,
                  providerType: providerType ?? undefined,
                }
              : undefined,
          };
        });

        // Merge older messages with existing ones (prepend)
        const mergedMessages = mergeOlderMessages(currentMessages, olderMessages);

        // Update state
        setHasOlderMessages(res.has_more ?? false);
        setCurrentChat({ chatId, allMessages: mergedMessages });

        // Save to cache with updated pagination
        const userKey = user?.email;
        await saveChatToCache(chatId, mergedMessages, 20, userKey, {
          hasMore: res.has_more ?? false,
          total: res.total ?? mergedMessages.length,
          offset: mergedMessages.length,
        });

        // Restore scroll position after DOM update
        requestAnimationFrame(() => {
          const newScrollHeight = container.scrollHeight;
          const heightDiff = newScrollHeight - prevScrollHeight;
          container.scrollTop = prevScrollTop + heightDiff;
        });
      }
    } catch (err) {
      logger.error("Failed to load older messages:", err);
    } finally {
      setIsLoadingOlder(false);
      loadingOlderRef.current = false;
    }
  }, [chatId, currentChat?.allMessages, hasOlderMessages, isLoadingOlder, setCurrentChat, user?.email]);

  // IntersectionObserver for loading older messages when scrolling up
  useEffect(() => {
    const sentinel = topSentinelRef.current;
    const container = containerRef.current;

    if (!sentinel || !container || !hasOlderMessages || !chatId) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const [entry] = entries;
        if (entry.isIntersecting && hasOlderMessages && !isLoadingOlder && !loadingOlderRef.current) {
          loadOlderMessages();
        }
      },
      {
        root: container,
        rootMargin: "100px 0px 0px 0px", // Trigger 100px before reaching the top
        threshold: 0.1,
      }
    );

    observer.observe(sentinel);

    return () => {
      observer.disconnect();
    };
  }, [hasOlderMessages, isLoadingOlder, loadOlderMessages, chatId]);

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
      className="h-full w-full px-3 overflow-y-auto"
      style={{ WebkitOverflowScrolling: "touch" }}
    >
      <div ref={contentRef} className="mx-auto space-y-5 pt-4 pb-4">
        {/* Top sentinel for loading older messages */}
        {hasOlderMessages && currentChat?.allMessages?.length ? (
          <div ref={topSentinelRef} className="h-1" data-top-sentinel />
        ) : null}

        {/* Loading indicator for older messages */}
        {isLoadingOlder && (
          <div className="flex justify-center py-4">
            <div className="flex items-center gap-2 text-gray-500 text-sm">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <span>Loading older messages...</span>
            </div>
          </div>
        )}

        {showLoading && !currentChat?.allMessages?.length ? (
          <div className="py-6 px-2">
            <SkeletonChatConversation messages={2} />
          </div>
        ) : currentChat?.allMessages.length === 0 ? (
          <p>No messages found</p>
        ) : (
          currentChat?.allMessages.map((message) => (
          <div key={message.id}>
            <div>
              <Bubble variant="user" content={message.userMessage} />
              {message.sentAt && (
                <p className="text-xs text-text-tertiary mt-0.5 mr-1 text-right">
                  {formatMessageTime(message.sentAt)}
                </p>
              )}
            </div>
            <div>
              <Bubble
                variant="bot"
                content={message.botMessage}
                streaming={message.streaming}
                stopped={message.stopped}
                statusMessage={message.statusMessage}
              />
              {message.respondedAt && (
                <p className="text-xs text-text-tertiary mt-0.5 ml-1">
                  {formatMessageTime(message.respondedAt)}
                </p>
              )}
            </div>
            {/* chat Actions */}
            {
              !message.streaming &&
              <div className="flex items-center gap-1 ml-2 mt-1 pb-1">
                <ChatAction
                  type="thumbsUp"
                  active={message.feedback === 'positive' || (activeFeedback.messageId === message.id && activeFeedback.feedbackType === 'positive')}
                  onClick={() => handleFeedbackClick(message.id, 'positive')}
                />
                <ChatAction
                  type="thumbsDown"
                  active={message.feedback === 'negative' || (activeFeedback.messageId === message.id && activeFeedback.feedbackType === 'negative')}
                  onClick={() => handleFeedbackClick(message.id, 'negative')}
                />
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
            {activeFeedback.messageId === message.id && (
              <InlineFeedback
                feedbackType={activeFeedback.feedbackType}
                onSubmit={handleFeedbackSubmit}
                onCancel={handleFeedbackCancel}
                isLoading={feedbackLoading}
              />
            )}
          </div>
        ))
      )}
      <div ref={bottomRef} data-bottom-marker />
      {
        chatId == undefined && currentChat == null && (
          <div className="flex items-center justify-center min-h-[60vh]">
            <p className="text-lg md:text-2xl text-text-secondary">
              How can I help you today?
            </p>
          </div>
        )
      }

      </div>
      </div>
  );
};

export default ChatView;

import Bubble from "../components/ui/Bubble";
import { useParams } from "react-router-dom";
import { useAuthContext } from "../hooks/useAuthContext";
import { useEffect, useState } from "react";
import { getChatMessagesById } from "../handlers/chatHandler";
import { useSidebarContext } from "../hooks/useSidebarContext";

const ChatView = () => {
  const { chatId } = useParams<{ chatId: string }>();
  const { user } = useAuthContext();
  const { currentChat, setCurrentChat } = useSidebarContext();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!user || !chatId) return;
    setLoading(true);
    const fetchMessages = async () => {
      try {
        const res = await getChatMessagesById(user?.token, chatId);
        if (res && Array.isArray(res)) {
          const messages = res.map((message: any) => ({
            id: message.id,
            userMessage: message.user_query || "",
            botMessage: message.bot_solution || "",
          }));
          setCurrentChat({
            chatId: chatId,
            allMessages: messages,
          });
        } else {
          setCurrentChat({
            chatId: chatId,
            allMessages: [],
          });
        }
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
    return()=>{
      setCurrentChat(null);
    }
  }, [chatId, user]);

  if (!user) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-lg md:text-2xl">Please login to view the chat</p>
      </div>
    );
  }

  return (
    <div className={`flex-1 space-y-4 overflow-y-auto px-3`}>
      {loading ? (
        <p>Loading messages...</p>
      ) : currentChat?.allMessages.length === 0 ? (
        <p>No messages found</p>
      ) : (
        currentChat?.allMessages.map((message) => (
          <div key={message.id}>
            <Bubble
              key={message.id + "-user"}
              variant="user"
              content={message.userMessage}
            />
            <Bubble
              key={message.id + "-bot"}
              variant="bot"
              content={message.botMessage}
            />
          </div>
        ))
      )}
    </div>
  );
};

export default ChatView;

import { useState, useRef } from "react";
import Navbar from "../components/Navbar";
import Sidebar from "../components/Sidebar";
import InputBox from "../components/ui/InputBox";
import { SendStopButton } from "../components/ui/SendStopButton";
import { useSidebarContext } from "../hooks/useSidebarContext";
import { Outlet, useNavigate, useParams } from "react-router-dom";
import { newMessageHandler } from "../handlers/chatHandler";
import type { ChatSSEEvent } from "../handlers/chatHandler";
import { useAuthContext } from "../hooks/useAuthContext";

function ChatPage() {
  const { isSidebarOpen, setCurrentChat } = useSidebarContext();
  const [chatInput, setChatInput] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const { chatId } = useParams<{ chatId: string }>();
  const { user } = useAuthContext();
  const navigate = useNavigate();

  const handlePromptSend = async () => {
    console.log("Sending prompt...");
    const prompt = chatInput;
    console.log("Prompt:", prompt);
    if (!prompt || !user) {
      console.error("Invalid prompt or user");
      return;
    }

    // Create new AbortController for this request
    abortControllerRef.current = new AbortController();
    
    setChatInput("");
    const currChatId = chatId || "";
    const newMessageId = Date.now().toString();

    try {
      setCurrentChat((prevChat:any) => ({
        chatId: currChatId,
        allMessages: [
          ...(prevChat?.allMessages ?? []),
          {
            id: newMessageId,
            userMessage: prompt,
            botMessage: "Thinking...",
          },
        ],
      }));

      setIsLoading(true);

      const res = await newMessageHandler(
        currChatId, 
        prompt, 
        user?.token, 
        (evt: ChatSSEEvent) => {
          if (!evt) return;
        if (evt.label) {
          setCurrentChat((prevChat:any) => ({
            ...prevChat,
            allMessages: prevChat?.allMessages?.map((m:any) =>
              m.id === newMessageId ? { ...m, botMessage: evt.label } : m
            ),
          }));
        }
      },
      abortControllerRef.current
      );
      console.log("res: ", res);

      if (currChatId === "") {
        navigate(`/${res.chatId}`);
        return;
      }

      setCurrentChat((prevChat:any) => ({
        chatId: res.chatId,
        allMessages: prevChat?.allMessages.map((message:any) =>
          message.id === newMessageId
            ? { ...message, botMessage: res.new_message }
            : message
        ),
      }));

      setIsLoading(false);
    } catch (err: any) {
      console.error("Error sending prompt:", err);
      setIsLoading(false);
      
      // Handle aborted request
      if (err.name === 'AbortError' || err.message === 'Request aborted') {
        console.log("Request was aborted");
        // Optionally update the UI to show the request was stopped
        setCurrentChat((prevChat:any) => ({
          ...prevChat,
          allMessages: prevChat?.allMessages.map((message:any) =>
            message.id === newMessageId 
              ? { ...message, botMessage: "Request stopped by user" }
              : message
          ),
        }));
      }
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  };

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsLoading(false);
      console.log("Request aborted by user");
    }
  };

  return (
    <div className={`flex h-screen`}>
      <Sidebar />
      <div className={`flex-1 ${isSidebarOpen && "hidden md:block"}`}>
        <div className="flex flex-col h-screen">
          <Navbar />
          <div className="flex-1 min-h-0 overflow-y-auto">
            <Outlet />
          </div>
          {/* Prompt Box */}
          <div className="flex items-end p-5 gap-x-3 bg-gray-50 w-full">
            <InputBox
              className="flex-1"
              onChange={(value) => {
                setChatInput(value);
              }}
              value={chatInput}
              placeholder="Type your message..."
              variant="multiline"
              backgroundColor="f9fafb"
              rows={1}
              maxHeight={180}
              // Enter -> Send
              // onKeyDown={(e) => {
              //   if (e.key === 'Enter' && !e.shiftKey) {
              //     e.preventDefault();
              //     if (!isLoading && chatInput.trim()) {
              //       handlePromptSend();
              //     }
              //   }
              // }}
            />
            <SendStopButton
              isLoading={isLoading}
              onSend={handlePromptSend}
              onStop={handleStop}
              disabled={false}
              inputValue={chatInput}
              className="flex-none py-0 px-4 h-11 rounded-xl mb-1.5"
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export default ChatPage;

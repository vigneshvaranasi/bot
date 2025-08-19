import { useState, useRef } from "react";
import Navbar from "../components/Navbar";
import Sidebar from "../components/Sidebar";
import InputBox from "../components/ui/InputBox";
import { Button } from "../components/ui/Button";
import { useSidebarContext } from "../hooks/useSidebarContext";
import { Outlet, useNavigate, useParams } from "react-router-dom";
import { newMessageHandler } from "../handlers/chatHandler";
import type { ChatSSEEvent } from "../handlers/chatHandler";
import { useAuthContext } from "../hooks/useAuthContext";

function ChatPage() {
  const { isSidebarOpen, setCurrentChat } = useSidebarContext();
  const [chatInput, setChatInput] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const sendBtnRef = useRef<HTMLButtonElement>(null);
  const { chatId } = useParams<{ chatId: string }>();
  const { user } = useAuthContext();
  const navigate = useNavigate();

  const handlePromptSend = async () => {
    console.log("Sending prompt...");
    sendBtnRef.current?.setAttribute("disabled", "true");
    const prompt = chatInput;
    console.log("Prompt:", prompt);
    if (!prompt || !user) {
      console.error("Invalid prompt or user");
      return;
    }
    setChatInput("");
    try {
      let currChatId = chatId || "";
      const newMessageId = Date.now().toString();

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

      const res = await newMessageHandler(currChatId, prompt, user?.token, (evt: ChatSSEEvent) => {
        if (!evt) return;
        if (evt.label) {
          setCurrentChat((prevChat:any) => ({
            ...prevChat,
            allMessages: prevChat?.allMessages?.map((m:any) =>
              m.id === newMessageId ? { ...m, botMessage: evt.label } : m
            ),
          }));
        }
      });
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
    } catch (err) {
      console.error("Error sending prompt:", err);
      setIsLoading(false);
    } finally {
      setIsLoading(false);
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
            <Button
              ref={sendBtnRef}
              variant="secondary"
              onClick={handlePromptSend}
              disabled={isLoading || !chatInput.trim()}
              className="flex-none h-11 py-0 px-4 rounded-xl"
            >
              Send
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ChatPage;

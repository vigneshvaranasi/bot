import { useState, useRef } from "react";
import Navbar from "../components/Navbar";
import Sidebar from "../components/Sidebar";
import InputBox from "../components/ui/InputBox";
import { Button } from "../components/ui/Button";
import { useSidebarContext } from "../hooks/useSidebarContext";
import { Outlet, useNavigate, useParams } from "react-router-dom";
import { newMessageHandler } from "../handlers/chatHandler";
import { useAuthContext } from "../hooks/useAuthContext";

function ChatPage() {
  const { isSidebarOpen, setCurrentChat, currentChat } = useSidebarContext();
  const [chatInput, setChatInput] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const promptInputRef = useRef<HTMLInputElement>(null);
  const sendBtnRef = useRef<HTMLButtonElement>(null);
  const { chatId } = useParams<{ chatId: string }>();
  const { user } = useAuthContext();
  const navigate = useNavigate();

  const handlePromptSend = async () => {
    console.log('Sending prompt...');
    sendBtnRef.current?.setAttribute("disabled", "true");
    const prompt = chatInput;
    console.log('Prompt:', prompt);
    if (!prompt || !user) {
      console.error("Invalid prompt or user");
      return;
    }
    setChatInput("");
    try {
      let currChatId = chatId || "";      
      setCurrentChat({
        chatId: currChatId,
        allMessages: [
          ...(currentChat?.allMessages ?? []),
          {
            id: Date.now().toString(),
            userMessage: prompt,
            botMessage: "",
          },
        ],
      });
      setIsLoading(true);
      const res = await newMessageHandler(currChatId, prompt, user?.token);
      console.log('res: ', res);
      if(currChatId==""){
        navigate(`/${res.chatId}`);
        return;
      }
      let previousMessages = currentChat?.allMessages ?? [];
      previousMessages[previousMessages.length - 1].botMessage = res.new_message;
      console.log('previousMessages: ', previousMessages);
      setCurrentChat({
        chatId: res.chatId,
        allMessages: previousMessages,
      });
      setIsLoading(false);
      
      // until this is recieved we have to stop the input and button
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
          <Outlet />
          {/* Prompt Box */}
          <div className="flex p-5 gap-x-2 bg-gray-50 w-full">
            <InputBox
              onChange={(value) => {
                setChatInput(value);
              }}
              value={chatInput}
              placeholder="Type your message..."
              variant="primary"
              backgroundColor="f9fafb"
            />
            <Button
              ref={sendBtnRef}
              variant="secondary"
              onClick={handlePromptSend}
              disabled={isLoading || !chatInput.trim()}
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

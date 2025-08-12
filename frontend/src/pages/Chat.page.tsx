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

      // Fetch the bot's response
      const res = await newMessageHandler(currChatId, prompt, user?.token);
      console.log("res: ", res);

      if (currChatId === "") {
        navigate(`/${res.chatId}`);
        return;
      }

      // Update the "Thinking..." message with the bot's response
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

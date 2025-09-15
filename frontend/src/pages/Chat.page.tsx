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
import { formatDuration,saveChatMetrics } from "../utils/metrics";

function ChatPage() {
  const { isSidebarOpen, setCurrentChat, triggerRefreshChats } = useSidebarContext();
  const [chatInput, setChatInput] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const sendBtnRef = useRef<HTMLButtonElement>(null);
  const { chatId } = useParams<{ chatId: string }>();
  const { user } = useAuthContext();
  const navigate = useNavigate();

  const handlePromptSend = async () => {
    // console.log("Sending prompt...");
    sendBtnRef.current?.setAttribute("disabled", "true");
    const prompt = chatInput;
    // console.log("Prompt:", prompt);
    if (!prompt || !user) {
      console.error("Invalid prompt or user");
      return;
    }
    setChatInput("");
    try {
      let currChatId = chatId || "";
      const newMessageId = Date.now().toString();
      const t0 = performance.now();
      let firstChunkAt: number | null = null;
      let firstTokenAt: number | null = null;
      let endAt: number | null = null;

  setCurrentChat((prevChat:any) => ({
        chatId: currChatId,
        allMessages: [
          ...(prevChat?.allMessages ?? []),
          {
            id: newMessageId,
            userMessage: prompt,
            botMessage: "Thinking...",
            streaming: true,
          },
        ],
      }));

      setIsLoading(true);

  const res = await newMessageHandler(currChatId, prompt, user?.token, (evt: ChatSSEEvent) => {
        if (!evt) return;
        // Capture first chunk 
        if (firstChunkAt === null && evt.event !== "answer_stream_done") {
          firstChunkAt = performance.now();
        }
        if (evt.event === "answer_stream") {
          // Buffer the full streamed answer for proper Markdown rendering
          let chunk = typeof evt.data?.text === 'string' ? evt.data.text : '';
          // Capture first token
          if (firstTokenAt === null) {
            firstTokenAt = performance.now();
          }
          setCurrentChat((prevChat:any) => {
            const updatedMessages = prevChat?.allMessages?.map((m:any) => {
              if (m.id === newMessageId) {
                // Use a buffer to accumulate the full answer for Markdown rendering
                let buffer = m._streamBuffer || '';
                if (!m._finalAnswerStarted) {
                  // Remove a single leading code fence (if present)
                  chunk = chunk.replace(/^```[a-zA-Z0-9]*\n?/, '');
                  buffer = chunk;
                  return {
                    ...m,
                    botMessage: buffer,
                    streaming: true,
                    _finalAnswerStarted: true,
                    _streamBuffer: buffer,
                  };
                } else {
                  // Remove a single trailing code fence (if present)
                  chunk = chunk.replace(/```$/, '');
                  buffer += chunk;
                  return {
                    ...m,
                    botMessage: buffer,
                    streaming: true,
                    _streamBuffer: buffer,
                  };
                }
              }
              return m;
            });
            return {
              ...prevChat,
              allMessages: updatedMessages,
            };
          });
        } else if (evt.event === "answer_stream_done") {
          endAt = performance.now();
          const totalMs = Math.round(endAt - t0);
          const ttfChunkMs = firstChunkAt ? Math.round(firstChunkAt - t0) : null;
          const ttfTokenMs = firstTokenAt ? Math.round(firstTokenAt - t0) : null;
          console.log(
            [
              ttfChunkMs !== null ? `Time to first chunk: ${formatDuration(ttfChunkMs)}` : undefined,
              ttfTokenMs !== null ? `Time to first token: ${formatDuration(ttfTokenMs)}` : undefined,
              `Response time: ${formatDuration(totalMs)}`,
            ]
              .filter(Boolean)
              .join("\n")
          );
          setCurrentChat((prevChat:any) => ({
            ...prevChat,
            allMessages: prevChat?.allMessages?.map((m:any) =>
              m.id === newMessageId
                ? { ...m, streaming: false, _finalAnswerDone: true }
                : m
            ),
          }));
        } else if (
          evt.label &&
          ![
            "Saving conversation to your history",
            "Conversation saved successfully"
          ].includes(evt.label)
        ) {
          // For other events, update the message but preserve streaming state
          setCurrentChat((prevChat:any) => ({
            ...prevChat,
            allMessages: prevChat?.allMessages?.map((m:any) => {
              if (m.id === newMessageId) {
                if (m._finalAnswerStarted || m._finalAnswerDone) return m;
                return { ...m, botMessage: evt.label || "", streaming: true };
              }
              return m;
            }),
          }));
        }
      });
      // console.log("res: ", res);

      // Compute metrics
      const metrics = {
        timeToFirstChunk: firstChunkAt ? Math.round(firstChunkAt - t0) : undefined,
        timeToFirstToken: firstTokenAt ? Math.round(firstTokenAt - t0) : undefined,
        totalResponseTime: Math.round((endAt ?? performance.now()) - t0),
      };

      if (currChatId === "") {
        // store new chat metrics in session storage
        if (res?.chatId) {
          saveChatMetrics(res.chatId, metrics);
        }
        triggerRefreshChats();
        navigate(`/${res.chatId}`);
        return;
      }

      setCurrentChat((prevChat:any) => ({
        chatId: res.chatId,
        allMessages: prevChat?.allMessages.map((message:any) =>
          message.id === newMessageId
            ? { ...message, botMessage: res.new_message, streaming: false, responseMetrics: metrics }
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
              className="flex-none py-0 px-4 h-11 rounded-xl mb-1.5"
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

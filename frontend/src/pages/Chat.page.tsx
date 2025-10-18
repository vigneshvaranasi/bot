import { useState, useRef, useEffect } from "react";
import Navbar from "../components/Navbar";
import Sidebar from "../components/Sidebar";
import InputBox from "../components/ui/InputBox";
import { Button } from "../components/ui/Button";
import { useSidebarContext } from "../hooks/useSidebarContext";
import { Outlet, useNavigate, useParams } from "react-router-dom";
import {
  newMessageHandler,
  // newMessageHandlerNoStream,
} from "../handlers/chatHandler";
import type { ChatSSEEvent } from "../handlers/chatHandler";
import { useAuthContext } from "../hooks/useAuthContext";
import { saveChatMetrics } from "../utils/metrics";
import { saveChatToCache } from "../utils/chatCache";
import micOn from "../assets/chat/micOn.svg";
import micOff from "../assets/chat/micOff.svg";

function ChatPage() {
  const { isSidebarOpen, setCurrentChat, currentChat, triggerRefreshChats } =
    useSidebarContext();
  const [chatInput, setChatInput] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // Speech recognition states
  const recognitionRef = useRef<any>(null);
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [hasSpeechSupport, setHasSpeechSupport] = useState<boolean>(false);

  const { chatId } = useParams<{ chatId: string }>();
  const { user } = useAuthContext();
  const navigate = useNavigate();

  // check Web Speech API support
  useEffect(() => {
    const SR: any =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;
    setHasSpeechSupport(!!SR);
  }, []);

  // const handlePromptSendNoStream = async (overridePrompt?: string) => {
  //   const prompt = (overridePrompt ?? chatInput).trim();
  //   if (!prompt || !user) {
  //     console.error("Invalid prompt or user");
  //     return;
  //   }
  //   setChatInput("");
  //   try {
  //     let currChatId = chatId || "";
  //     const newMessageId = Date.now().toString();
  //     setCurrentChat((prevChat: any) => ({
  //       chatId: currChatId,
  //       allMessages: [
  //         ...(prevChat?.allMessages ?? []),
  //         {
  //           id: newMessageId,
  //           userMessage: prompt,
  //           botMessage: "Thinking...",
  //           streaming: true,
  //         },
  //       ],
  //     }));
  //     setIsLoading(true);

  //     const res = await newMessageHandlerNoStream(
  //       currChatId,
  //       prompt,
  //       user?.token
  //     );

  //     if (currChatId === "") {
  //       triggerRefreshChats();
  //       navigate(`/${res.chat_id}`);
  //       return;
  //     }
  //     setCurrentChat((prevChat: any) => {
  //       const updatedMessages = prevChat?.allMessages?.map((message: any) =>
  //         message.id === newMessageId
  //           ? {
  //               ...message,
  //               botMessage: res.response,
  //               streaming: false,
  //             }
  //           : message
  //       );
  //       return {
  //         chatId: res.chat_id,
  //         allMessages: updatedMessages,
  //       };
  //     });
  //   } catch (err) {
  //     console.error("Error sending prompt:", err);
  //   } finally {
  //     setIsLoading(false);
  //   }
  // };

  const handlePromptSendStream = async (overridePrompt?: string) => {
    const prompt = (overridePrompt ?? chatInput).trim();
    if (!prompt || !user) {
      console.error("Invalid prompt or user");
      return;
    }
    setChatInput("");

    try {
      const t0 = performance.now();
      // let firstChunkAt: number | null = null;
      let firstTokenAt: number | null = null;
      let endAt: number | null = null;
      let currChatId = chatId || "";
      console.log("currChatId: ", currChatId);

      const newMessageId = Date.now().toString();
      // todo: Performance metrics

      setCurrentChat((prevChat: any) => ({
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

      const res = await newMessageHandler(
        currChatId,
        prompt,
        user?.token,
        (evt: ChatSSEEvent) => {
          if (!evt) return;

          if (evt.event === "final_answer") {
            let chunk = evt.data.chunk;
            setCurrentChat((prevChat: any) => {
              const updatedMessages = prevChat?.allMessages?.map((m: any) => {
                if (m.id === newMessageId) {
                  // Use a buffer to accumulate the full answer for Markdown rendering
                  let buffer = m._streamBuffer || "";
                  if (!m._finalAnswerStarted) {
                    // Remove a single leading code fence (if present)
                    chunk = chunk.replace(/^```[a-zA-Z0-9]*\n?/, "");
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
                    // FIRST CHUNK
                    firstTokenAt = performance.now();
                    chunk = chunk.replace(/```$/, "");
                    console.log(chunk);
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
          } else if (evt.event === "status") {
            // Update Stream
            setCurrentChat((prevChat: any) => ({
              ...prevChat,
              allMessages: prevChat?.allMessages?.map((m: any) => {
                if (m.id === newMessageId) {
                  if (m._finalAnswerStarted || m._finalAnswerDone) return m;
                  return {
                    ...m,
                    botMessage: evt.data.message || "",
                    streaming: true,
                  };
                }
                return m;
              }),
            }));
          } else if (evt.event === "complete") {
            // FINAL CHUNK
            endAt = performance.now();

            // Compute metrics
            const metrics = {
              timeToFirstToken: firstTokenAt
                ? Math.round(firstTokenAt - t0)
                : undefined,
              totalResponseTime: Math.round((endAt ?? performance.now()) - t0),
            };
            console.log("metrics: ", metrics);
            setCurrentChat((prevChat: any) => ({
              ...prevChat,
              allMessages: prevChat?.allMessages?.map((m: any) => {
                if (m.id === newMessageId) {
                  return {
                    ...m,
                    streaming: false,
                    _finalAnswerDone: true,
                    responseMetrics: metrics,
                  };
                }
                return m;
              }),
            }));
          }
        }
      );
      const metrics = {
        timeToFirstToken: firstTokenAt
          ? Math.round(firstTokenAt - t0)
          : undefined,
        totalResponseTime: Math.round(endAt! - t0),
      };
      if (currChatId === "") {
        if (res?.chat_id) {
          saveChatMetrics(res.chat_id, metrics);
        }
        triggerRefreshChats();
        navigate(`/${res.chat_id}`);
        return;
      }



      try {
        const toCache = currentChat?.allMessages.map((m:any) => ({
          id: m.id,
          userMessage: m.userMessage,
          botMessage: m.botMessage,
          responseMetrics: m.responseMetrics,
        }));
        await saveChatToCache(res.chat_id, toCache!, 20, user?.email);
      } catch {}
    } catch (error) {

    } finally {
      setIsLoading(false);
    }
  };

  // Speach recognition handler
  const toggleDictation = () => {
    if (!hasSpeechSupport) return;
    if (isRecording) {
      setIsRecording(false);
      try {
        recognitionRef.current?.stop?.();
      } catch {}
      return;
    }

    const SR: any =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;
    if (!SR) return;
    const recognition = new SR();
    recognitionRef.current = recognition;
    recognition.lang = (navigator as any).language || "en-US";
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognition.continuous = true;

    const baseText = chatInput.trim();
    let finalTranscript = "";

    recognition.onstart = () => {
      setIsRecording(true);
    };
    recognition.onerror = (event: any) => {
      console.warn("Speech recognition error:", event?.error || event);
    };
    recognition.onresult = (event: any) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const res = event.results[i];
        const text = res[0]?.transcript ?? "";
        if (res.isFinal) finalTranscript += text;
        else interim += text;
      }
      const composed = [baseText, finalTranscript, interim]
        .filter(Boolean)
        .join(" ")
        .replace(/\s+/g, " ")
        .trim();
      setChatInput(composed);
    };
    recognition.onend = () => {
      setIsRecording(false);
      const composed = [baseText, finalTranscript]
        .filter(Boolean)
        .join(" ")
        .replace(/\s+/g, " ")
        .trim();
      if (composed) setChatInput(composed);
    };

    try {
      recognition.start();
    } catch (e) {
      console.warn("Unable to start speech recognition:", e);
      setIsRecording(false);
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
              placeholder={
                isRecording
                  ? "Listening… release mic to edit"
                  : "Type your message..."
              }
              variant="multiline"
              backgroundColor="f9fafb"
              rows={1}
              maxHeight={180}
              readOnly={isRecording}
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
            {hasSpeechSupport && (
              <Button
                variant="secondary"
                onClick={toggleDictation}
                disabled={isLoading}
                className={`flex-none h-11 rounded-xl mb-1.5 flex items-center justify-center ${
                  isRecording ? "animate-pulse" : ""
                }`}
              >
                {!isRecording ? (
                  <img src={micOn} alt="Stop dictation" className="w-5" />
                ) : (
                  <img src={micOff} alt="Start dictation" className="w-5" />
                )}
              </Button>
            )}
            <Button
              variant="secondary"
              // onClick={() => handlePromptSend()}
              // onClick={() => handlePromptSendNoStream()}
              onClick={() => handlePromptSendStream()}
              disabled={isRecording || isLoading || !chatInput.trim()}
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

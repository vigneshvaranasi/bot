import { useState, useRef, useEffect } from "react";
import InputBox from "./ui/InputBox";
import SendIcon from "./icons/SendIcon";
import StopIcon from "./icons/StopIcon";
import { fetchAvailableModels } from "../handlers/llmProviderHandlers";
import { fetchAiMlSettings } from "../handlers/settingsHandlers";
import type { AvailableModel } from "../types/LlmProvider";
import { logger } from "../utils/logger";

// Web Speech API type declarations (vendor-prefixed for browser compatibility)
interface SpeechRecognitionResult {
  readonly isFinal: boolean;
  readonly length: number;
  item(index: number): SpeechRecognitionAlternative;
  [index: number]: SpeechRecognitionAlternative;
}

interface SpeechRecognitionAlternative {
  readonly transcript: string;
  readonly confidence: number;
}

interface SpeechRecognitionResultList {
  readonly length: number;
  item(index: number): SpeechRecognitionResult;
  [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionEvent extends Event {
  readonly resultIndex: number;
  readonly results: SpeechRecognitionResultList;
}

interface SpeechRecognitionErrorEvent extends Event {
  readonly error: string;
  readonly message: string;
}

interface SpeechRecognitionInstance extends EventTarget {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  onstart: ((this: SpeechRecognitionInstance, ev: Event) => void) | null;
  onend: ((this: SpeechRecognitionInstance, ev: Event) => void) | null;
  onerror: ((this: SpeechRecognitionInstance, ev: SpeechRecognitionErrorEvent) => void) | null;
  onresult: ((this: SpeechRecognitionInstance, ev: SpeechRecognitionEvent) => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

interface SpeechRecognitionConstructor {
  new (): SpeechRecognitionInstance;
}

const getSpeechRecognition = (): SpeechRecognitionConstructor | undefined => {
  const w = window as Window & {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };
  return w.SpeechRecognition || w.webkitSpeechRecognition;
};

export interface ModelOverride {
  provider_id: string;
  model_id: string;
}

interface PromptBarProps {
  onSend: (prompt: string, modelOverride?: ModelOverride) => void;
  onStop?: () => void;
  isLoading: boolean;
  canStop?: boolean;
  focusKey?: string | number;
}

export default function PromptBar({ onSend, onStop, isLoading, canStop, focusKey }: PromptBarProps) {
  const [chatInput, setChatInput] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [hasSpeechSupport, setHasSpeechSupport] = useState(false);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement | null>(null);

  // Model selector state
  const [models, setModels] = useState<AvailableModel[]>([]);
  const [selectedModel, setSelectedModel] = useState<AvailableModel | null>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [showModelPicker, setShowModelPicker] = useState(false);
  const [autoRoutingEnabled, setAutoRoutingEnabled] = useState(false);
  const [userExplicitlyPickedModel, setUserExplicitlyPickedModel] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputFocusedRef = useRef(false);

  // Check speech support
  useEffect(() => {
    setHasSpeechSupport(!!getSpeechRecognition());
  }, []);

  // Fetch available models and saved settings on mount
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [modelsRes, settingsRes] = await Promise.all([
        fetchAvailableModels(),
        fetchAiMlSettings(),
      ]);
      if (cancelled) return;
      const allModels = modelsRes?.models ?? [];
      setModels(allModels);

      setShowModelPicker(settingsRes?.settings?.allow_user_model_selection ?? false);
      setAutoRoutingEnabled(settingsRes?.settings?.auto_routing_enabled ?? false);

      // Match the admin-configured model + provider from settings
      const savedModelId = settingsRes?.settings?.model;
      const savedProviderId = settingsRes?.settings?.provider_id;
      const savedMatch = savedModelId
        ? allModels.find((m) =>
            m.model_id === savedModelId &&
            (!savedProviderId || m.provider_id === savedProviderId)
          )
        : null;

      const defaultModel =
        savedMatch ??
        allModels.find((m) => m.is_default_provider) ??
        allModels[0] ??
        null;
      setSelectedModel(defaultModel);
    })();
    return () => { cancelled = true; };
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);
  useEffect(() => {
    if (typeof document === "undefined") return;
    const active = document.activeElement as HTMLElement | null;
    const activeTag = active?.tagName?.toLowerCase();
    const isTypingElsewhere =
      activeTag === "input" ||
      activeTag === "textarea" ||
      activeTag === "select" ||
      active?.isContentEditable;
    if (isTypingElsewhere && active !== inputRef.current) return;
    setTimeout(() => inputRef.current?.focus?.(), 0);
  }, [focusKey]);

  // Group models by provider
  const grouped = models.reduce<Record<string, AvailableModel[]>>((acc, m) => {
    (acc[m.provider_name] ??= []).push(m);
    return acc;
  }, {});

  const handleSend = () => {
    const text = chatInput.trim();
    if (!text || isLoading) return;
    const shouldOverride = selectedModel && (!autoRoutingEnabled || userExplicitlyPickedModel);
    const override: ModelOverride | undefined = shouldOverride
      ? { provider_id: selectedModel.provider_id, model_id: selectedModel.model_id }
      : undefined;
    onSend(text, override);
    setChatInput("");
  };

  const handleInputFocus: React.FocusEventHandler<HTMLInputElement | HTMLTextAreaElement> = () => {
    if (typeof window === "undefined") return;
    inputFocusedRef.current = true;
    const isMobile = window.matchMedia("(max-width: 767px)").matches;
    if (!isMobile) return;
    window.scrollTo({ top: 0, left: 0 });
  };

  // Speech recognition
  const toggleDictation = () => {
    if (!hasSpeechSupport) return;
    if (isRecording) {
      setIsRecording(false);
      try { recognitionRef.current?.stop?.(); } catch { /* ignore */ }
      return;
    }

    const SR = getSpeechRecognition();
    if (!SR) return;
    const recognition = new SR();
    recognitionRef.current = recognition;
    recognition.lang = navigator.language || "en-US";
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognition.continuous = true;

    const baseText = chatInput.trim();
    let finalTranscript = "";

    recognition.onstart = () => setIsRecording(true);
    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      logger.warn("Speech recognition error:", event.error);
    };
    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const res = event.results[i];
        const text = res[0]?.transcript ?? "";
        if (res.isFinal) finalTranscript += text;
        else interim += text;
      }
      const composed = [baseText, finalTranscript, interim]
        .filter(Boolean).join(" ").replace(/\s+/g, " ").trim();
      setChatInput(composed);
    };
    recognition.onend = () => {
      setIsRecording(false);
      const composed = [baseText, finalTranscript]
        .filter(Boolean).join(" ").replace(/\s+/g, " ").trim();
      if (composed) setChatInput(composed);
    };

    try {
      recognition.start();
    } catch (e) {
      logger.warn("Unable to start speech recognition:", e);
      setIsRecording(false);
    }
  };

  return (
    <div className="w-full px-4 py-2 md:py-3 prompt-bar-safe">
      {/* Model selector pill */}
      {models.length > 0 && (showModelPicker || autoRoutingEnabled) && (
        <div className="relative mb-1.5" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => setDropdownOpen((v) => !v)}
            className={`inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-lg border transition-colors  
                border-border-default bg-surface-primary hover:bg-surface-tertiary text-text-secondary`}
          >
            {autoRoutingEnabled && !userExplicitlyPickedModel
              ? "Auto"
              : (selectedModel?.display_name ?? "Select model")}
            <svg width="12" height="12" viewBox="0 0 20 20" fill="currentColor" className={`transition-transform ${dropdownOpen ? "rotate-180" : ""}`}>
              <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
            </svg>
          </button>

          {dropdownOpen && (
            <div className="absolute left-0 bottom-full mb-1 z-50 w-64 max-h-72 overflow-y-auto rounded-lg border border-border-default bg-surface-primary shadow-dropdown">
              {autoRoutingEnabled && (
                <button
                  type="button"
                  onClick={() => {
                    setUserExplicitlyPickedModel(false);
                    setDropdownOpen(false);
                  }}
                  className={`w-full text-left px-3 py-2 text-sm transition-colors border-b border-border-default text-text-primary hover:bg-surface-tertiary`}
                >
                  Auto
                </button>
              )}
              {Object.entries(grouped).map(([providerName, providerModels]) => (
                <div key={providerName}>
                  <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-text-tertiary bg-surface-secondary">
                    {providerName}
                  </div>
                  {providerModels.map((m) => (
                    <button
                      key={`${m.provider_id}-${m.model_id}`}
                      type="button"
                      onClick={() => {
                        setSelectedModel(m);
                        setUserExplicitlyPickedModel(true);
                        setDropdownOpen(false);
                      }}
                      className={`w-full text-left px-3 py-2 text-sm hover:bg-surface-tertiary transition-colors ${
                        selectedModel?.provider_id === m.provider_id && selectedModel?.model_id === m.model_id
                          ? "bg-accent-subtle text-accent font-medium"
                          : "text-text-primary"
                      }`}
                    >
                      {m.display_name}
                    </button>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Input row */}
      <div className="flex items-end gap-x-2 mx-auto">
        <InputBox
          className="flex-1"
          onChange={(value) => setChatInput(value)}
          onFocus={handleInputFocus}
          value={chatInput}
          placeholder={isRecording ? "Listening... release mic to edit" : "Type your message..."}
          variant="multiline"
          backgroundColor="surface-secondary"
          rows={1}
          maxHeight={180}
          readOnly={isRecording}
          inputRef={inputRef}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
        />
        {hasSpeechSupport && (
          <button
            onClick={toggleDictation}
            disabled={isLoading}
            className={`flex-none h-10 w-10 rounded-xl mb-1.5 flex items-center justify-center cursor-pointer transition-colors ${
              isRecording
                ? "border border-red-300 bg-red-50 text-red-600 animate-pulse"
                : "border border-border-default bg-surface-primary hover:bg-surface-tertiary text-text-secondary"
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {!isRecording ? (
              <svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" fill="none" className="w-5 h-5">
                <g fill="currentColor">
                  <path fillRule="evenodd" d="M8 0c-.78 0-1.538.29-2.104.821A2.797 2.797 0 005 2.861V8.14c0 .775.328 1.507.896 2.04.566.53 1.323.821 2.104.821.78 0 1.538-.29 2.104-.821A2.797 2.797 0 0011 8.139V2.86c0-.775-.329-1.507-.896-2.04A3.077 3.077 0 008 0zM6.922 1.915A1.578 1.578 0 018 1.5c.413 0 .8.154 1.078.415.276.26.422.601.422.946V8.14c0 .345-.146.686-.422.946A1.578 1.578 0 018 9.5c-.413 0-.8-.154-1.078-.415-.276-.26-.422-.601-.422-.946V2.86c0-.345.146-.686.422-.946z" clipRule="evenodd" />
                  <path d="M4 6.75a.75.75 0 00-1.5 0v1.385a5.3 5.3 0 001.619 3.801A5.553 5.553 0 007.25 13.45v1.05H5.5a.75.75 0 000 1.5h5a.75.75 0 000-1.5H8.75v-1.05a5.553 5.553 0 003.131-1.514A5.3 5.3 0 0013.5 8.135V6.75a.75.75 0 00-1.5 0v1.385a3.8 3.8 0 01-1.164 2.725A4.071 4.071 0 018 12a4.071 4.071 0 01-2.836-1.14A3.8 3.8 0 014 8.135V6.75z" />
                </g>
              </svg>
            ) : (
              <svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" fill="none" className="w-5 h-5">
                <g fill="currentColor">
                  <path d="M8 0c-.78 0-1.538.29-2.104.821a2.862 2.862 0 00-.627.857.75.75 0 001.354.644c.07-.147.17-.286.3-.407A1.578 1.578 0 018 1.5c.413 0 .8.154 1.078.415.276.26.422.601.422.946v3.443a.75.75 0 001.5 0V2.861c0-.775-.329-1.507-.896-2.04A3.077 3.077 0 008 0z" />
                  <path fillRule="evenodd" d="M5 6.06L1.22 2.28a.75.75 0 011.06-1.06l12.5 12.5a.75.75 0 11-1.06 1.06L11.338 12.4a5.575 5.575 0 01-2.588 1.05V14.5h1.75a.75.75 0 010 1.5h-5a.75.75 0 010-1.5h1.75v-1.05a5.553 5.553 0 01-3.131-1.514A5.3 5.3 0 012.5 8.135V6.75a.75.75 0 011.5 0v1.385a3.8 3.8 0 001.164 2.725A4.071 4.071 0 008 12c.815 0 1.602-.24 2.262-.677l-.726-.726A3.113 3.113 0 018 11c-.78 0-1.538-.29-2.104-.821A2.797 2.797 0 015 8.139V6.06zm1.5 1.5v.579c0 .345.146.686.422.946.278.26.665.415 1.078.415.134 0 .266-.016.392-.047L6.5 7.56z" clipRule="evenodd" />
                  <path d="M12.03 6.75a.75.75 0 011.5 0v1.385c0 .266-.02.53-.06.79a.75.75 0 11-1.483-.227c.029-.185.043-.374.043-.563V6.75z" />
                </g>
              </svg>
            )}
          </button>
        )}
        {canStop ? (
          <button
            onClick={onStop}
            className="flex-none h-10 w-10 rounded-xl mb-1.5 flex items-center justify-center cursor-pointer transition-colors bg-accent hover:bg-accent-hover text-text-inverse"
          >
            <StopIcon size={18} />
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={isRecording || isLoading || !chatInput.trim()}
            className={`flex-none h-10 w-10 rounded-xl mb-1.5 flex items-center justify-center cursor-pointer transition-colors ${
              isRecording || isLoading || !chatInput.trim()
                ? "bg-surface-tertiary text-text-tertiary cursor-not-allowed"
                : "bg-accent hover:bg-accent-hover text-text-inverse"
            }`}
          >
            <SendIcon size={18} />
          </button>
        )}
      </div>
    </div>
  );
}

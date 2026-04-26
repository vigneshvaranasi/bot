import { useCallback, useEffect, useState } from "react";
import type { TourStep } from "../components/GuidedTour";

const STORAGE_PREFIX = "supportbot:tour:chat:done:";

const storageKey = (userKey?: string | null) =>
  `${STORAGE_PREFIX}${userKey || "anonymous"}`;

export function buildChatTourSteps(opts: {
  hasModelPicker: boolean;
  hasSpeechSupport: boolean;
}): TourStep[] {
  const steps: TourStep[] = [
    {
      id: "welcome",
      title: "Welcome to Support Bot",
      body:
        "A quick 60 second tour of the chat workspace. You can press Esc anytime to exit.",
    },
    {
      id: "new-chat",
      selector: '[data-tour="new-chat"]',
      title: "Start a new conversation",
      body:
        "Use this to spin up a fresh thread whenever you switch context - each chat keeps its own history.",
      placement: "right",
      ensureSidebarOpen: true,
    },
    {
      id: "search",
      selector: '[data-tour="sidebar-search"]',
      title: "Find an old chat",
      body:
        "Type a few words from a past chat to jump right back into it.",
      placement: "right",
      ensureSidebarOpen: true,
    },
    {
      id: "history",
      selector: '[data-tour="sidebar-history"]',
      title: "Your chat history",
      body:
        "Recent chats live here. Hover any chat to rename or archive it from the menu.",
      placement: "right",
      ensureSidebarOpen: true,
    },
    {
      id: "theme",
      selector: '[data-tour="theme-toggle"]',
      title: "Light or dark, your call",
      body: "Toggle the theme to whatever feels easier on the eyes right now.",
      placement: "top",
      ensureSidebarOpen: true,
    },
  ];

  if (opts.hasModelPicker) {
    steps.push({
      id: "model-picker",
      selector: '[data-tour="model-picker"]',
      title: "Pick the right model",
      body:
        "Choose which model answers your message. Leave it on Auto and we'll pick the best one for you.",
      placement: "top",
      ensureSidebarClosed: true,
    });
  }

  steps.push({
    id: "prompt-input",
    selector: '[data-tour="prompt-input"]',
    title: "Ask anything",
    body:
      "Type your question and hit Enter. Use Shift + Enter to add a new line.",
    placement: "top",
    ensureSidebarClosed: true,
  });

  if (opts.hasSpeechSupport) {
    steps.push({
      id: "prompt-mic",
      selector: '[data-tour="prompt-mic"]',
      title: "Or just talk",
      body:
        "Tap the mic to speak your message instead of typing.",
      placement: "top",
      ensureSidebarClosed: true,
    });
  }

  steps.push({
    id: "send",
    selector: '[data-tour="prompt-send"]',
    title: "Send when ready",
    body:
      "Click here or press Enter to send. You can stop a reply mid-stream any time.",
    placement: "top",
    ensureSidebarClosed: true,
  });

  steps.push({
    id: "done",
    title: "You're all set",
    body:
      "Need this tour again later? Click the help icon at the bottom of the sidebar to replay it.",
  });

  return steps;
}

export function hasCompletedChatTour(userKey?: string | null): boolean {
  if (typeof window === "undefined") return true;
  try {
    return localStorage.getItem(storageKey(userKey)) === "1";
  } catch {
    return true;
  }
}

export function markChatTourComplete(userKey?: string | null) {
  try {
    localStorage.setItem(storageKey(userKey), "1");
  } catch {
    // ignore
  }
}

export function resetChatTour(userKey?: string | null) {
  try {
    localStorage.removeItem(storageKey(userKey));
  } catch {
    // ignore
  }
}

export function useChatTour(opts: {
  userKey: string | null | undefined;
  ready: boolean;
}) {
  const { userKey, ready } = opts;
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (!ready || !userKey) return;
    if (hasCompletedChatTour(userKey)) return;
    const t = setTimeout(() => setIsOpen(true), 450);
    return () => clearTimeout(t);
  }, [ready, userKey]);

  const start = useCallback(() => setIsOpen(true), []);
  const dismiss = useCallback(() => {
    setIsOpen(false);
    markChatTourComplete(userKey);
  }, [userKey]);
  const complete = useCallback(() => {
    setIsOpen(false);
    markChatTourComplete(userKey);
  }, [userKey]);

  return { isOpen, start, dismiss, complete };
}
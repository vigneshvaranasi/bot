import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "motion/react";

export type TourPlacement = "top" | "bottom" | "left" | "right" | "auto";

export type TourStep = {
  id: string;
  selector?: string;
  title: string;
  body: string;
  placement?: TourPlacement;
  padding?: number;
  ensureSidebarOpen?: boolean;
  ensureSidebarClosed?: boolean;
  hideOnMobile?: boolean;
  onlyIf?: () => boolean;
};

interface GuidedTourProps {
  steps: TourStep[];
  isOpen: boolean;
  onComplete: () => void;
  onSkip: () => void;
  onSidebarVisibility?: (open: boolean) => void;
}

const CARD_GAP = 14;
const CARD_HEIGHT_ESTIMATE = 200;
const VIEWPORT_PADDING = 16;
const HIGHLIGHT_RADIUS = 10;

function getCardWidth() {
  if (typeof window === "undefined") return 340;
  return Math.min(340, window.innerWidth - VIEWPORT_PADDING * 2);
}

function isMobileViewport() {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(max-width: 767px)").matches;
}

function getRect(selector: string): DOMRect | null {
  const el = document.querySelector(selector) as HTMLElement | null;
  if (!el) return null;
  const rect = el.getBoundingClientRect();
  if (rect.width === 0 && rect.height === 0) return null;
  return rect;
}

async function waitForElement(selector: string, timeoutMs = 800): Promise<DOMRect | null> {
  const start = performance.now();
  while (performance.now() - start < timeoutMs) {
    const rect = getRect(selector);
    if (rect) return rect;
    await new Promise((r) => requestAnimationFrame(() => r(null)));
  }
  return getRect(selector);
}

type CardPosition = {
  top: number;
  left: number;
  arrow: { side: "top" | "bottom" | "left" | "right"; offset: number } | null;
};

function computeCardPosition(
  rect: DOMRect | null,
  placement: TourPlacement,
  cardWidth: number,
  cardHeight: number
): CardPosition {
  const vw = window.innerWidth;
  const vh = window.innerHeight;

  if (!rect) {
    return {
      top: Math.max(VIEWPORT_PADDING, vh / 2 - cardHeight / 2),
      left: Math.max(VIEWPORT_PADDING, vw / 2 - cardWidth / 2),
      arrow: null,
    };
  }

  const spaceTop = rect.top;
  const spaceBottom = vh - rect.bottom;
  const spaceLeft = rect.left;
  const spaceRight = vw - rect.right;

  let chosen: "top" | "bottom" | "left" | "right" = "bottom";
  if (placement && placement !== "auto") {
    chosen = placement;
  } else {
    const cands: Array<["top" | "bottom" | "left" | "right", number]> = [
      ["bottom", spaceBottom],
      ["top", spaceTop],
      ["right", spaceRight],
      ["left", spaceLeft],
    ];
    cands.sort((a, b) => b[1] - a[1]);
    chosen = cands[0][0];
  }

  let top = 0;
  let left = 0;
  let arrowSide: "top" | "bottom" | "left" | "right" = "top";
  let arrowOffset = 24;

  if (chosen === "bottom") {
    top = rect.bottom + CARD_GAP;
    left = rect.left + rect.width / 2 - cardWidth / 2;
    arrowSide = "top";
    arrowOffset = Math.min(Math.max(cardWidth / 2 - 8, 24), cardWidth - 32);
  } else if (chosen === "top") {
    top = rect.top - cardHeight - CARD_GAP;
    left = rect.left + rect.width / 2 - cardWidth / 2;
    arrowSide = "bottom";
    arrowOffset = Math.min(Math.max(cardWidth / 2 - 8, 24), cardWidth - 32);
  } else if (chosen === "right") {
    top = rect.top + rect.height / 2 - cardHeight / 2;
    left = rect.right + CARD_GAP;
    arrowSide = "left";
    arrowOffset = Math.min(Math.max(cardHeight / 2 - 8, 24), cardHeight - 32);
  } else {
    top = rect.top + rect.height / 2 - cardHeight / 2;
    left = rect.left - cardWidth - CARD_GAP;
    arrowSide = "right";
    arrowOffset = Math.min(Math.max(cardHeight / 2 - 8, 24), cardHeight - 32);
  }

  if (left < VIEWPORT_PADDING) {
    if (arrowSide === "top" || arrowSide === "bottom") {
      arrowOffset = Math.max(16, rect.left + rect.width / 2 - VIEWPORT_PADDING);
    }
    left = VIEWPORT_PADDING;
  }
  if (left + cardWidth > vw - VIEWPORT_PADDING) {
    const overflow = left + cardWidth - (vw - VIEWPORT_PADDING);
    left -= overflow;
    if (arrowSide === "top" || arrowSide === "bottom") {
      arrowOffset = Math.min(cardWidth - 16, arrowOffset + overflow);
    }
  }
  if (top < VIEWPORT_PADDING) {
    if (arrowSide === "left" || arrowSide === "right") {
      arrowOffset = Math.max(16, rect.top + rect.height / 2 - VIEWPORT_PADDING);
    }
    top = VIEWPORT_PADDING;
  }
  if (top + cardHeight > vh - VIEWPORT_PADDING) {
    const overflow = top + cardHeight - (vh - VIEWPORT_PADDING);
    top -= overflow;
    if (arrowSide === "left" || arrowSide === "right") {
      arrowOffset = Math.min(cardHeight - 16, arrowOffset + overflow);
    }
  }

  return { top, left, arrow: { side: arrowSide, offset: arrowOffset } };
}

export default function GuidedTour({
  steps,
  isOpen,
  onComplete,
  onSkip,
  onSidebarVisibility,
}: GuidedTourProps) {
  const [stepIndex, setStepIndex] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const [cardSize, setCardSize] = useState({ w: getCardWidth(), h: CARD_HEIGHT_ESTIMATE });
  const [ready, setReady] = useState(false);
  const cardRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const onResize = () => {
      setCardSize((prev) => ({ ...prev, w: getCardWidth() }));
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const activeSteps = useMemo(() => {
    const mobile = isMobileViewport();
    return steps.filter((s) => {
      if (s.hideOnMobile && mobile) return false;
      if (s.onlyIf && !s.onlyIf()) return false;
      return true;
    });
  }, [steps]);

  const step = activeSteps[stepIndex];
  const isLast = stepIndex === activeSteps.length - 1;
  const isFirst = stepIndex === 0;

  useEffect(() => {
    if (isOpen) {
      setStepIndex(0);
      setReady(false);
      setCardSize({ w: getCardWidth(), h: CARD_HEIGHT_ESTIMATE });
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen || !step) return;
    if (step.ensureSidebarOpen) onSidebarVisibility?.(true);
    else if (step.ensureSidebarClosed) onSidebarVisibility?.(false);
  }, [isOpen, step, onSidebarVisibility]);

  useEffect(() => {
    if (!isOpen || !step) return;
    let cancelled = false;
    setReady(false);
    (async () => {
      await new Promise((r) => requestAnimationFrame(() => r(null)));
      await new Promise((r) => setTimeout(r, 120));
      if (cancelled) return;
      if (!step.selector) {
        setRect(null);
        setReady(true);
        return;
      }
      const r = await waitForElement(step.selector);
      if (cancelled) return;
      setRect(r);
      setReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [isOpen, step]);

  useEffect(() => {
    if (!isOpen || !step?.selector) return;
    const update = () => {
      const r = getRect(step.selector!);
      if (r) setRect(r);
    };
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);

    const t1 = setTimeout(update, 80);
    const t2 = setTimeout(update, 200);
    const t3 = setTimeout(update, 360);
    const t4 = setTimeout(update, 520);

    const target = document.querySelector(step.selector) as HTMLElement | null;
    let ro: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver(update);
      if (target) ro.observe(target);
      ro.observe(document.body);
    }

    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      clearTimeout(t4);
      ro?.disconnect();
    };
  }, [isOpen, step]);

  useLayoutEffect(() => {
    if (!ready || !cardRef.current) return;
    const h = cardRef.current.offsetHeight;
    if (!h) return;
    setCardSize((prev) => (prev.h === h ? prev : { ...prev, h }));
  }, [ready, stepIndex, step]);

  const next = useCallback(() => {
    if (isLast) {
      onComplete();
    } else {
      setStepIndex((i) => Math.min(i + 1, activeSteps.length - 1));
    }
  }, [isLast, activeSteps.length, onComplete]);

  const prev = useCallback(() => {
    setStepIndex((i) => Math.max(i - 1, 0));
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onSkip();
      } else if (e.key === "ArrowRight" || e.key === "Enter") {
        e.preventDefault();
        next();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        prev();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen, next, prev, onSkip]);

  if (!isOpen || !step) return null;

  const cardPos = computeCardPosition(rect, step.placement ?? "auto", cardSize.w, cardSize.h);
  const padding = step.padding ?? 8;

  const spotlightStyle: React.CSSProperties | null = rect
    ? {
      position: "fixed",
      top: rect.top - padding,
      left: rect.left - padding,
      width: rect.width + padding * 2,
      height: rect.height + padding * 2,
      borderRadius: HIGHLIGHT_RADIUS,
      boxShadow: "0 0 0 9999px rgba(8, 10, 18, 0.62)",
      pointerEvents: "none",
      transition: "all 0.32s cubic-bezier(0.16, 1, 0.3, 1)",
      zIndex: 9998,
    }
    : null;

  const ringStyle: React.CSSProperties | null = rect
    ? {
      position: "fixed",
      top: rect.top - padding,
      left: rect.left - padding,
      width: rect.width + padding * 2,
      height: rect.height + padding * 2,
      borderRadius: HIGHLIGHT_RADIUS,
      pointerEvents: "none",
      transition: "all 0.32s cubic-bezier(0.16, 1, 0.3, 1)",
      zIndex: 9999,
    }
    : null;

  return createPortal(
    <AnimatePresence>
      <motion.div
        key="guided-tour-root"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.18 }}
        className="fixed inset-0 z-[9990]"
        aria-live="polite"
        role="dialog"
      >
        {!rect && (
          <div
            className="fixed inset-0"
            style={{ background: "rgba(8, 10, 18, 0.62)", zIndex: 9990 }}
            onClick={onSkip}
          />
        )}

        {spotlightStyle && <div style={spotlightStyle} />}

        {ringStyle && (
          <motion.div
            style={{
              ...ringStyle,
              border: "1.5px solid var(--color-accent)",
            }}
            initial={{ opacity: 0.85 }}
            animate={{ opacity: [0.85, 0.35, 0.85] }}
            transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
          />
        )}

        {ready && (
          <motion.div
            ref={cardRef}
            key={step.id}
            initial={{ opacity: 0, y: 8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.98 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            style={{
              position: "fixed",
              top: cardPos.top,
              left: cardPos.left,
              width: cardSize.w,
              maxWidth: "calc(100vw - 32px)",
              zIndex: 10000,
            }}
            className="rounded-xl border border-border-default bg-surface-primary shadow-2xl overflow-hidden"
          >
            {cardPos.arrow && rect && (
              <div
                aria-hidden
                style={{
                  position: "absolute",
                  width: 12,
                  height: 12,
                  background: "var(--color-surface-primary)",
                  border: "1px solid var(--color-border-default)",
                  transform: "rotate(45deg)",
                  ...(cardPos.arrow.side === "top" && {
                    top: -7,
                    left: cardPos.arrow.offset,
                    borderRight: "none",
                    borderBottom: "none",
                  }),
                  ...(cardPos.arrow.side === "bottom" && {
                    bottom: -7,
                    left: cardPos.arrow.offset,
                    borderLeft: "none",
                    borderTop: "none",
                  }),
                  ...(cardPos.arrow.side === "left" && {
                    left: -7,
                    top: cardPos.arrow.offset,
                    borderRight: "none",
                    borderTop: "none",
                  }),
                  ...(cardPos.arrow.side === "right" && {
                    right: -7,
                    top: cardPos.arrow.offset,
                    borderLeft: "none",
                    borderBottom: "none",
                  }),
                }}
              />
            )}

            <div className="px-5 pt-4 pb-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-medium uppercase tracking-[0.08em] text-text-tertiary">
                  Step {stepIndex + 1} / {activeSteps.length}
                </span>
                <button
                  type="button"
                  onClick={onSkip}
                  className="text-text-tertiary hover:text-text-primary transition-colors text-xs"
                >
                  Skip
                </button>
              </div>
              <h3 className="mt-2 text-[15px] font-semibold text-text-primary leading-snug">
                {step.title}
              </h3>
              <p className="mt-1.5 text-[13px] leading-relaxed text-text-secondary">
                {step.body}
              </p>
            </div>

            <div className="px-5 pb-3 flex items-center gap-1.5">
              {activeSteps.map((s, i) => (
                <span
                  key={s.id}
                  className="h-1 rounded-full transition-all duration-300"
                  style={{
                    width: i === stepIndex ? 20 : 6,
                    background:
                      i <= stepIndex
                        ? "var(--color-accent)"
                        : "var(--color-border-default)",
                    opacity: i === stepIndex ? 1 : i < stepIndex ? 0.55 : 1,
                  }}
                />
              ))}
            </div>

            <div className="flex items-center justify-between gap-2 px-4 py-2.5 border-t border-border-default bg-surface-secondary">
              <button
                type="button"
                onClick={prev}
                disabled={isFirst}
                className={`px-3 py-1.5 text-sm rounded-md transition-colors ${isFirst
                    ? "text-text-tertiary cursor-not-allowed"
                    : "text-text-secondary hover:text-text-primary hover:bg-surface-tertiary"
                  }`}
              >
                Back
              </button>
              <button
                type="button"
                onClick={next}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-sm font-medium rounded-md bg-accent text-text-inverse hover:bg-accent-hover transition-colors active:scale-[0.98]"
              >
                {isLast ? "Got it" : "Next"}
                {!isLast && (
                  <svg
                    width="13"
                    height="13"
                    viewBox="0 0 20 20"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2.2}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M5 10h10M11 6l4 4-4 4" />
                  </svg>
                )}
              </button>
            </div>
          </motion.div>
        )}
      </motion.div>
    </AnimatePresence>,
    document.body
  );
}
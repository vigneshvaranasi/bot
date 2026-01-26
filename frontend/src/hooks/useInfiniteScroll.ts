import { useEffect, useRef, useCallback } from "react";

export interface UseInfiniteScrollOptions {
  /** Callback when scroll threshold is reached */
  onLoadMore: () => Promise<void>;
  /** Whether there are more items to load */
  hasMore: boolean;
  /** Whether currently loading */
  isLoading: boolean;
  /** Scroll direction - 'up' for chat messages (reverse), 'down' for standard lists */
  direction: "up" | "down";
  /** Threshold percentage (0-1) - 0.8 means trigger at 80% scrolled */
  threshold?: number;
  /** Debounce delay in ms */
  debounceMs?: number;
}

export interface UseInfiniteScrollReturn {
  /** Attach to sentinel element at the loading edge */
  sentinelRef: React.RefObject<HTMLDivElement>;
  /** Attach to the scrollable container */
  containerRef: React.RefObject<HTMLDivElement>;
}

/**
 * Generic infinite scroll hook using IntersectionObserver.
 * Supports both forward (scroll down to load more) and reverse (scroll up to load older) scrolling.
 */
export function useInfiniteScroll({
  onLoadMore,
  hasMore,
  isLoading,
  direction,
  threshold = 0.8,
  debounceMs = 150,
}: UseInfiniteScrollOptions): UseInfiniteScrollReturn {
  const sentinelRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const loadingRef = useRef(false);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Memoized load handler with deduplication
  const handleLoadMore = useCallback(async () => {
    // Prevent concurrent loads
    if (loadingRef.current || isLoading || !hasMore) return;

    loadingRef.current = true;
    try {
      await onLoadMore();
    } finally {
      loadingRef.current = false;
    }
  }, [onLoadMore, isLoading, hasMore]);

  // Debounced load trigger
  const debouncedLoadMore = useCallback(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }
    debounceTimerRef.current = setTimeout(() => {
      handleLoadMore();
    }, debounceMs);
  }, [handleLoadMore, debounceMs]);

  useEffect(() => {
    const sentinel = sentinelRef.current;
    const container = containerRef.current;

    if (!sentinel || !container) return;
    if (!hasMore) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const [entry] = entries;
        if (entry.isIntersecting && hasMore && !isLoading && !loadingRef.current) {
          debouncedLoadMore();
        }
      },
      {
        root: container,
        rootMargin: direction === "up" ? "100px 0px 0px 0px" : "0px 0px 100px 0px",
        threshold: threshold,
      }
    );

    observer.observe(sentinel);

    return () => {
      observer.disconnect();
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [hasMore, isLoading, direction, threshold, debouncedLoadMore]);

  return {
    sentinelRef: sentinelRef as React.RefObject<HTMLDivElement>,
    containerRef: containerRef as React.RefObject<HTMLDivElement>,
  };
}

export default useInfiniteScroll;

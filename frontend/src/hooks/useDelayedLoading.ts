import { useState, useEffect, useRef, useCallback } from "react";

/**
 * Hook that delays showing a loading indicator until after a threshold.
 * Prevents flickering for fast loads while still showing loading state for slower operations.
 *
 * @param isLoading - The actual loading state
 * @param delay - Delay in ms before showing loading indicator (default: 150ms)
 * @returns showLoading - Whether to show the loading indicator
 */
export function useDelayedLoading(isLoading: boolean, delay: number = 150): boolean {
  const [showLoading, setShowLoading] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (isLoading) {
      // Start a timer - only show loading if it takes longer than delay
      timeoutRef.current = setTimeout(() => {
        setShowLoading(true);
      }, delay);
    } else {
      // Loading finished - clear timeout and hide loading
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      setShowLoading(false);
    }

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [isLoading, delay]);

  return showLoading;
}

/**
 * Hook for managing loading state with delayed indicator.
 * Returns loading controls and a delayed showLoading flag.
 *
 * @param delay - Delay in ms before showing loading indicator (default: 150ms)
 */
export function useLoadingState(delay: number = 150) {
  const [isLoading, setIsLoading] = useState(false);
  const showLoading = useDelayedLoading(isLoading, delay);

  const startLoading = useCallback(() => setIsLoading(true), []);
  const stopLoading = useCallback(() => setIsLoading(false), []);

  return {
    isLoading,
    showLoading,
    startLoading,
    stopLoading,
    setIsLoading,
  };
}

export default useDelayedLoading;

import { Toaster } from "react-hot-toast";
import { useTheme } from "../hooks/useTheme";

export function ThemedToaster() {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  return (
    <Toaster
      position="top-center"
      toastOptions={{
        duration: 3000,
        style: {
          borderRadius: "8px",
          background: isDark ? "#1e2028" : "#ffffff",
          color: isDark ? "#e5e7eb" : "#121212",
          fontSize: "14px",
          fontWeight: "500",
          border: `1px solid ${isDark ? "#2a2d36" : "#e5e7eb"}`,
          boxShadow: isDark
            ? "0 4px 6px -1px rgb(0 0 0 / 0.4), 0 2px 4px -2px rgb(0 0 0 / 0.3)"
            : "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
          padding: "12px 16px",
        },
        success: {
          iconTheme: {
            primary: isDark ? "#34d399" : "#059669",
            secondary: isDark ? "#0f1117" : "#ffffff",
          },
        },
        error: {
          iconTheme: {
            primary: isDark ? "#f87171" : "#dc2626",
            secondary: isDark ? "#0f1117" : "#ffffff",
          },
        },
      }}
    />
  );
}

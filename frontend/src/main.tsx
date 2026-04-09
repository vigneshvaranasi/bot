import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.tsx";
import { BrowserRouter } from "react-router-dom";
import { SidebarProvider } from "./store/SidebarContext.tsx";
import AuthProvider from "./store/AuthProvider.tsx";
import { PermissionProvider } from "./store/PermissionProvider.tsx";
import { FileProvider } from "./store/FileProvider.tsx";
import { ThemeProvider } from "./store/ThemeProvider.tsx";
import { ThemedToaster } from "./components/ThemedToaster.tsx";

createRoot(document.getElementById("root")!).render(
  <ThemeProvider>
    <AuthProvider>
      <PermissionProvider>
        <FileProvider>
          <BrowserRouter>
            <SidebarProvider>
              <App />
              <ThemedToaster />
            </SidebarProvider>
          </BrowserRouter>
        </FileProvider>
      </PermissionProvider>
    </AuthProvider>
  </ThemeProvider>
);

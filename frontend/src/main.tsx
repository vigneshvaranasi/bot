import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.tsx";
import { BrowserRouter } from "react-router-dom";
import { SidebarProvider } from "./store/SidebarContext.tsx";
import AuthProvider from "./store/AuthProvider.tsx";
import { PermissionProvider } from "./store/PermissionProvider.tsx";
import { FileProvider } from "./store/FileProvider.tsx";
import { Toaster } from "react-hot-toast";

createRoot(document.getElementById("root")!).render(
  <AuthProvider>
    <PermissionProvider>
      <FileProvider>
        <BrowserRouter>
          <SidebarProvider>
            <App />
            <Toaster position="top-center" toastOptions={{ duration: 3000 }} />
          </SidebarProvider>
        </BrowserRouter>
      </FileProvider>
    </PermissionProvider>
  </AuthProvider>
);

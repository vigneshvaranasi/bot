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
            <Toaster
              position="top-center"
              toastOptions={{
                duration: 3000,
                style: {
                  borderRadius: '8px',
                  background: '#ffffff',
                  color: '#121212',
                  fontSize: '14px',
                  fontWeight: '500',
                  border: '1px solid #e5e7eb',
                  boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
                  padding: '12px 16px',
                },
                success: {
                  iconTheme: { primary: '#059669', secondary: '#ffffff' },
                },
                error: {
                  iconTheme: { primary: '#dc2626', secondary: '#ffffff' },
                },
              }}
            />
          </SidebarProvider>
        </BrowserRouter>
      </FileProvider>
    </PermissionProvider>
  </AuthProvider>
);

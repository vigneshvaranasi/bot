import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.tsx";
import { BrowserRouter } from "react-router-dom";
import { SidebarProvider } from "./store/SidebarContext.tsx";
import AuthProvider from "./store/AuthProvider.tsx";
import { FileProvider } from "./store/FileProvider.tsx";

createRoot(document.getElementById("root")!).render(
  <AuthProvider>
    <FileProvider>
      <BrowserRouter>
        <SidebarProvider>
          <App />
        </SidebarProvider>
      </BrowserRouter>
    </FileProvider>
  </AuthProvider>
);

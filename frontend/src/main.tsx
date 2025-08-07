import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.tsx";
import { BrowserRouter } from "react-router-dom";
import { SidebarProvider } from "./store/SidebarContext.tsx";

createRoot(document.getElementById("root")!).render(
    <BrowserRouter>
        <SidebarProvider>
            <App />
        </SidebarProvider>
    </BrowserRouter>
);

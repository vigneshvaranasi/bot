import { useState } from "react";
import Sidebar from "../components/Sidebar";
import ChatView from "../view/ChatView";

function ChatPage() {
  const [isSidebarOpen, setSidebarOpen] = useState(true);
  return (
    <div className={`flex h-screen`}>
      <Sidebar isOpen={isSidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className={`flex-1`}>
        <ChatView />
      </div>
    </div>
  );
}

export default ChatPage;

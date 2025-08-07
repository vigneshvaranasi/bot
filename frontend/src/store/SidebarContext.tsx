import { createContext, useState } from "react";

type SidebarContextType = {
    isSidebarOpen: boolean;
    setSidebarOpen:React.Dispatch<React.SetStateAction<boolean>>;
};

export const SidebarContext = createContext<SidebarContextType>({
    isSidebarOpen: false,
    setSidebarOpen: () => {}
});

export const SidebarProvider = ({ children }: { children: React.ReactNode }) => {
    const [isSidebarOpen, setSidebarOpen] = useState(false);

    return (
        <SidebarContext.Provider value={{ isSidebarOpen, setSidebarOpen }}>
            {children}
        </SidebarContext.Provider>
    );
};


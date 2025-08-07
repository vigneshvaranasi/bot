import { useContext } from "react";
import { SidebarContext } from "../store/SidebarContext";

export const useSidebarContext = () => {
    const context = useContext(SidebarContext);
    if (context === null) {
        throw new Error("useSidebarContext must be used within a SidebarProvider");
    }
    return context;
};
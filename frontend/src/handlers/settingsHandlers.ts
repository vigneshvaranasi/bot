import { BE_URL } from "../config/config";
import type { Settings } from "../types/Settings";

export const fetchSettings = async () => {
    try{
        const response = await fetch(`${BE_URL}/settings/`, {
            method: "GET",
            headers: {
                "Content-Type": "application/json",
            }
        });
        console.log("Fetch settings response:", response);
        if (!response.ok) {
            throw new Error("Failed to fetch settings");
        }
        
        return response.json();
    }catch(error){
        console.error("Error fetching settings:", error);
        return null;
    }
};

export const updateSettings = async (settings: Settings, token: string) => {
    try{
        const response = await fetch(`${BE_URL}/settings/`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify(settings),
        });
        console.log("Update settings response:", response);
        if (!response.ok) {
            throw new Error("Failed to update settings");
        }
        
        return response.json();
    }catch(error){
        console.error("Error updating settings:", error);
        return null;
    }
};

export const rollbackSettings = async (token:string) => {
    try{

        const response = await fetch(`${BE_URL}/settings/rollback`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            }
        });
        console.log("Rollback settings response:", response);
        if (!response.ok) {
            throw new Error("Failed to rollback settings");
        }

        return response.json();
    }catch(error){
        console.error("Error rolling back settings:", error);
        return null;
    }
};
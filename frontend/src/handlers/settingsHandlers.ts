import { BE_URL } from "../config/config";
import type { Settings } from "../types/Settings";

export const fetchSettings = async () => {
    try {
        const response = await fetch(`${BE_URL}/settings/`, {
            method: "GET",
            headers: {
                "Content-Type": "application/json",
            }
        });

        if (!response.ok) {
            throw new Error("Failed to fetch settings");
        }

        const data = await response.json();
        return data;
    } catch (error) {
        console.error("Error fetching settings:", error);
        return null;
    }
};

export const updateSettings = async (settings: Settings, token: string) => {
    try {

        const response = await fetch(`${BE_URL}/settings/`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify(settings),
        });

        if (!response.ok) {
            throw new Error("Failed to update settings");
        }

        const data = await response.json();
        return data;
    } catch (error) {
        console.error("Error updating settings:", error);
        return null;
    }
};

export const rollbackSettings = async (token: string) => {
    try {

        const response = await fetch(`${BE_URL}/settings/rollback`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            }
        });
        if (!response.ok) {
            throw new Error("Failed to rollback settings");
        }

        return response.json();
    } catch (error) {
        console.error("Error rolling back settings:", error);
        return null;
    }
};
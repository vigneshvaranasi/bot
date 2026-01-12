import http from "../utils/http";
import { logger } from "../utils/logger";
import type { Settings } from "../types/Settings";

export const fetchSettings = async () => {
    try {
        const { data } = await http.get("/settings/");
        return data;
    } catch (error) {
        logger.error("Error fetching settings:", error);
        return null;
    }
};

export const updateSettings = async (settings: Partial<Settings>) => {
    try {
        const current = await fetchSettings();
        const merged: Partial<Settings> = {
            ...(current ?? {}),
            ...settings,
        };

        const { data } = await http.post("/settings/", merged);
        return data;
    } catch (error) {
        logger.error("Error updating settings:", error);
        return null;
    }
};

export const rollbackSettings = async () => {
    try {
        const { data } = await http.put("/settings/rollback");
        return data;
    } catch (error) {
        logger.error("Error rolling back settings:", error);
        return null;
    }
};
import http from "../utils/http";
import { logger } from "../utils/logger";
import type {
    Settings,
    AiMlSettings,
    AuthSettings,
    SegmentSettingResponse,
    SettingHistoryResponse,
} from "../types/Settings";

// ============================================================
// Legacy endpoints (for backward compatibility)
// ============================================================

export const fetchSettings = async (): Promise<Settings | null> => {
    try {
        const { data } = await http.get("/settings/");
        return data;
    } catch (error) {
        logger.error("Error fetching settings:", error);
        return null;
    }
};

export const updateSettings = async (settings: Partial<Settings>): Promise<Settings | null> => {
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

export const rollbackSettings = async (): Promise<Settings | null> => {
    try {
        const { data } = await http.put("/settings/rollback");
        return data;
    } catch (error) {
        logger.error("Error rolling back settings:", error);
        return null;
    }
};

// ============================================================
// Segment-based endpoints
// ============================================================

export const fetchAiMlSettings = async (): Promise<SegmentSettingResponse<AiMlSettings> | null> => {
    try {
        const { data } = await http.get("/settings/segment/aiml");
        return data;
    } catch (error) {
        logger.error("Error fetching AI/ML settings:", error);
        return null;
    }
};

export const updateAiMlSettings = async (
    settings: Partial<AiMlSettings>
): Promise<SegmentSettingResponse<AiMlSettings> | null> => {
    try {
        const { data } = await http.put("/settings/segment/aiml", settings);
        return data;
    } catch (error) {
        logger.error("Error updating AI/ML settings:", error);
        return null;
    }
};

export const fetchAuthSettings = async (): Promise<SegmentSettingResponse<AuthSettings> | null> => {
    try {
        const { data } = await http.get("/settings/segment/auth");
        return data;
    } catch (error) {
        logger.error("Error fetching Auth settings:", error);
        return null;
    }
};

export const updateAuthSettings = async (
    settings: Partial<AuthSettings>
): Promise<SegmentSettingResponse<AuthSettings> | null> => {
    try {
        const { data } = await http.put("/settings/segment/auth", settings);
        return data;
    } catch (error) {
        logger.error("Error updating Auth settings:", error);
        return null;
    }
};

// ============================================================
// History and rollback endpoints
// ============================================================

export const fetchSettingsHistory = async (
    limit: number = 50,
    offset: number = 0
): Promise<SettingHistoryResponse | null> => {
    try {
        const { data } = await http.get(`/settings/history?limit=${limit}&offset=${offset}`);
        return data;
    } catch (error) {
        logger.error("Error fetching settings history:", error);
        return null;
    }
};

export const rollbackToVersion = async (versionId: string): Promise<Settings | null> => {
    try {
        const { data } = await http.post(`/settings/rollback/${versionId}`);
        return data;
    } catch (error) {
        logger.error("Error rolling back to version:", error);
        return null;
    }
};

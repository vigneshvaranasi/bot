import http from "../utils/http";
import { logger } from "../utils/logger";
import type {
    Settings,
    AiMlSettings,
    AuthSettings,
    SegmentSettingResponse,
    SettingHistoryResponse,
    SettingSegment,
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

// Legacy rollbackSettings endpoint removed - use rollbackToVersion instead

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

/**
 * Fetch settings history with pagination and optional segment filter.
 *
 * @param limit - Maximum number of records (default 50).
 * @param offset - Number of records to skip (default 0).
 * @param segment - Optional segment filter ('aiml' or 'auth').
 * @returns Settings history with computed changes, or null on error.
 */
export const fetchSettingsHistory = async (
    limit: number = 50,
    offset: number = 0,
    segment?: SettingSegment
): Promise<SettingHistoryResponse | null> => {
    try {
        let url = `/settings/history?limit=${limit}&offset=${offset}`;
        if (segment) {
            url += `&segment=${segment}`;
        }
        const { data } = await http.get(url);
        return data;
    } catch (error) {
        logger.error("Error fetching settings history:", error);
        return null;
    }
};

/**
 * Rollback to a specific settings version.
 *
 * @param versionId - The UUID of the version to restore.
 * @param reason - Optional reason for the rollback (for audit trail).
 * @returns The new settings version, or null on error.
 */
export const rollbackToVersion = async (
    versionId: string,
    reason?: string
): Promise<Settings | null> => {
    try {
        const body = reason ? { reason } : undefined;
        const { data } = await http.post(`/settings/rollback/${versionId}`, body);
        return data;
    } catch (error) {
        logger.error("Error rolling back to version:", error);
        return null;
    }
};

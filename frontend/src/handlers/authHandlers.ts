import http from "../utils/http";
import { logger } from "../utils/logger";

export const updatePasswordHandler = async (password: string) => {
    try {
        const response = await http.post("/auth/password", { password });
        return response.data;
    } catch (error) {
        logger.error("Error updating password:", error);
        throw error;
    }
};

export const getAvailableProviders = async (): Promise<string[]> => {
    try {
        const response = await http.get<{ providers: string[] }>("/auth/providers");
        return response.data.providers;
    } catch (error) {
        logger.error("Error fetching providers:", error);
        throw error;
    }
};

export const initiateLinkProvider = async (provider: string): Promise<string> => {
    try {
        const response = await http.get<{ authorization_url: string }>(`/auth/link/${provider}`);
        return response.data.authorization_url;
    } catch (error) {
        logger.error("Error initiating provider link:", error);
        throw error;
    }
};

export const completeLinkProvider = async (provider: string, code: string, state: string) => {
    try {
        const params = new URLSearchParams({ code, state });
        const response = await http.get(`/auth/link/${provider}/callback?${params}`);
        return response.data;
    } catch (error) {
        logger.error("Error completing provider link:", error);
        throw error;
    }
};

export const unlinkProvider = async (provider: string) => {
    try {
        const response = await http.delete(`/auth/identities/${provider}`);
        return response.data;
    } catch (error) {
        logger.error("Error unlinking provider:", error);
        throw error;
    }
};
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
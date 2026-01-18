import http from "../utils/http";
import { logger } from "../utils/logger";
import type {
    LlmProvider,
    LlmProviderCreate,
    LlmProviderUpdate,
    LlmProviderListResponse,
    HealthCheckResult,
    AvailableModelsResponse,
} from "../types/LlmProvider";

/**
 * Fetch all LLM providers.
 *
 * @param activeOnly - If true, only return active providers.
 * @returns List of providers or null on error.
 */
export const fetchLlmProviders = async (
    activeOnly: boolean = false
): Promise<LlmProviderListResponse | null> => {
    try {
        const params = activeOnly ? "?active_only=true" : "";
        const { data } = await http.get(`/llm-providers/${params}`);
        return data;
    } catch (error) {
        logger.error("Error fetching LLM providers:", error);
        return null;
    }
};

/**
 * Fetch a single LLM provider by ID.
 *
 * @param providerId - UUID of the provider.
 * @returns Provider or null on error.
 */
export const fetchLlmProvider = async (
    providerId: string
): Promise<LlmProvider | null> => {
    try {
        const { data } = await http.get(`/llm-providers/${providerId}`);
        return data;
    } catch (error) {
        logger.error("Error fetching LLM provider:", error);
        return null;
    }
};

/**
 * Create a new LLM provider.
 *
 * @param payload - Provider creation data.
 * @returns Created provider or null on error.
 */
export const createLlmProvider = async (
    payload: LlmProviderCreate
): Promise<LlmProvider | null> => {
    try {
        const { data } = await http.post("/llm-providers/", payload);
        return data;
    } catch (error) {
        logger.error("Error creating LLM provider:", error);
        return null;
    }
};

/**
 * Update an existing LLM provider.
 *
 * @param providerId - UUID of the provider to update.
 * @param payload - Update data (partial).
 * @returns Updated provider or null on error.
 */
export const updateLlmProvider = async (
    providerId: string,
    payload: LlmProviderUpdate
): Promise<LlmProvider | null> => {
    try {
        const { data } = await http.put(`/llm-providers/${providerId}`, payload);
        return data;
    } catch (error) {
        logger.error("Error updating LLM provider:", error);
        return null;
    }
};

/**
 * Delete an LLM provider.
 *
 * @param providerId - UUID of the provider to delete.
 * @returns True if deleted, false on error.
 */
export const deleteLlmProvider = async (providerId: string): Promise<boolean> => {
    try {
        await http.delete(`/llm-providers/${providerId}`);
        return true;
    } catch (error) {
        logger.error("Error deleting LLM provider:", error);
        return false;
    }
};

/**
 * Test connection to an LLM provider.
 *
 * @param providerId - UUID of the provider to test.
 * @returns Health check result or null on error.
 */
export const testLlmProviderConnection = async (
    providerId: string
): Promise<HealthCheckResult | null> => {
    try {
        const { data } = await http.post(`/llm-providers/${providerId}/test`);
        return data;
    } catch (error) {
        logger.error("Error testing LLM provider connection:", error);
        return null;
    }
};

/**
 * Fetch all available models from active providers.
 *
 * @returns List of available models or null on error.
 */
export const fetchAvailableModels = async (): Promise<AvailableModelsResponse | null> => {
    try {
        const { data } = await http.get("/llm-providers/models/available");
        return data;
    } catch (error) {
        logger.error("Error fetching available models:", error);
        return null;
    }
};

/**
 * Set a provider as the default.
 *
 * @param providerId - UUID of the provider to set as default.
 * @returns Updated provider or null on error.
 */
export const setDefaultProvider = async (
    providerId: string
): Promise<LlmProvider | null> => {
    try {
        const { data } = await http.put(`/llm-providers/${providerId}`, {
            is_default: true,
        });
        return data;
    } catch (error) {
        logger.error("Error setting default provider:", error);
        return null;
    }
};

/**
 * Toggle provider active state.
 *
 * @param providerId - UUID of the provider.
 * @param isActive - New active state.
 * @returns Updated provider or null on error.
 */
export const toggleProviderActive = async (
    providerId: string,
    isActive: boolean
): Promise<LlmProvider | null> => {
    try {
        const { data } = await http.put(`/llm-providers/${providerId}`, {
            is_active: isActive,
        });
        return data;
    } catch (error) {
        logger.error("Error toggling provider active state:", error);
        return null;
    }
};

/**
 * Model discovery response.
 */
export interface ModelDiscoveryResponse {
    success: boolean;
    models: string[];
    message: string;
}

/**
 * Discover available models from a saved provider's API.
 *
 * @param providerId - UUID of the provider.
 * @returns Discovery result with list of models or null on error.
 */
export const discoverProviderModels = async (
    providerId: string
): Promise<ModelDiscoveryResponse | null> => {
    try {
        const { data } = await http.post(`/llm-providers/${providerId}/discover-models`);
        return data;
    } catch (error) {
        logger.error("Error discovering provider models:", error);
        return null;
    }
};

/**
 * Discover models from provider config without saving.
 * Use this for new providers before they are created.
 *
 * @param config - Provider configuration (same as create payload).
 * @returns Discovery result with list of models or null on error.
 */
export const discoverModelsFromConfig = async (
    config: LlmProviderCreate
): Promise<ModelDiscoveryResponse | null> => {
    try {
        const { data } = await http.post("/llm-providers/discover-models", config);
        return data;
    } catch (error) {
        logger.error("Error discovering models from config:", error);
        return null;
    }
};

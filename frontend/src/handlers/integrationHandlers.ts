import type { Integration } from "../types/Integrations";
import http from "../utils/http";
import { logger } from "../utils/logger";

export type IntegrationPayload = {
  service_name: string;
  auth_type: string;
  config: Record<string, string>;
  is_active: boolean;
};

export const fetchIntegrations = async (): Promise<Integration[] | null> => {
  try {
    const { data } = await http.get("/integrations/all");
    if (data?.success && Array.isArray(data.integrations)) {
      return data.integrations as Integration[];
    }
    return null;
  } catch (error) {
    logger.error("Error fetching integrations:", error);
    return null;
  }
};

export const createIntegration = async (
  payload: IntegrationPayload
): Promise<Integration | null> => {
  try {
    const { data } = await http.post("/integrations/create", payload);
    if (data?.success && data.integration) {
      return data.integration as Integration;
    }
    return null;
  } catch (error) {
    logger.error("Error creating integration:", error);
    return null;
  }
};

export const updateIntegration = async (
  integrationId: string,
  payload: IntegrationPayload
): Promise<Integration | null> => {
  try {
    const { data } = await http.put(`/integrations/update/${integrationId}`, payload);
    if (data?.success && data.integration) {
      return data.integration as Integration;
    }
    return null;
  } catch (error) {
    logger.error("Error updating integration:", error);
    return null;
  }
};

export const syncIntegration = async (
  integrationId: string
): Promise<Integration | null> => {
  try {
    const { data } = await http.post(`/integrations/sync/${integrationId}`);
    if (data?.success && data.integration) {
      return data.integration as Integration;
    }
    return null;
  } catch (error) {
    logger.error("Error syncing integration:", error);
    return null;
  }
};

export const deleteIntegration = async (
  integrationId: string
): Promise<boolean> => {
  try {
    const { data } = await http.delete(`/integrations/delete/${integrationId}`);
    return Boolean(data?.success);
  } catch (error) {
    logger.error("Error deleting integration:", error);
    return false;
  }
};

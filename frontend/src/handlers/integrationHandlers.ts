import type { Integration } from "../types/Integrations";
import http from "../utils/http";

export type IntegrationPayload = {
  service_name: string;
  auth_type: string;
  config: Record<string, string>;
  is_active: boolean;
};

export const fetchIntegrations = async (_token?: string): Promise<Integration[] | null> => {
  try {
    const { data } = await http.get("/integrations/all");
    if (data?.success && Array.isArray(data.integrations)) {
      return data.integrations as Integration[];
    }
    return null;
  } catch (error) {
    console.error("Error fetching integrations:", error);
    return null;
  }
};

export const createIntegration = async (
  payload: IntegrationPayload,
  _token?: string
): Promise<Integration | null> => {
  try {
    const { data } = await http.post("/integrations/create", payload);
    if (data?.success && data.integration) {
      return data.integration as Integration;
    }
    return null;
  } catch (error) {
    console.error("Error creating integration:", error);
    return null;
  }
};

export const updateIntegration = async (
  integrationId: string,
  payload: IntegrationPayload,
  _token?: string
): Promise<Integration | null> => {
  try {
    const { data } = await http.put(`/integrations/update/${integrationId}`, payload);
    if (data?.success && data.integration) {
      return data.integration as Integration;
    }
    return null;
  } catch (error) {
    console.error("Error updating integration:", error);
    return null;
  }
};

export const syncIntegration = async (
  integrationId: string,
  _token?: string
): Promise<Integration | null> => {
  try {
    const { data } = await http.post(`/integrations/sync/${integrationId}`);
    if (data?.success && data.integration) {
      return data.integration as Integration;
    }
    return null;
  } catch (error) {
    console.error("Error syncing integration:", error);
    return null;
  }
};

export const deleteIntegration = async (
  integrationId: string,
  _token?: string
): Promise<boolean> => {
  try {
    const { data } = await http.delete(`/integrations/delete/${integrationId}`);
    return Boolean(data?.success);
  } catch (error) {
    console.error("Error deleting integration:", error);
    return false;
  }
};

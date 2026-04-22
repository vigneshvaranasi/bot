import type { AuthType, ConnectorType, Integration } from "../types/Integrations";
import http from "../utils/http";
import { logger } from "../utils/logger";
import { BE_URL } from "../config/config";

export type IntegrationPayload = {
  service_name: string;
  connector_type: ConnectorType;
  auth_type: AuthType;
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

export type SyncProgressEvent = {
  batch: number;
  totalBatches: number;
  totalIncidents?: number;
  incidents?: string[];
  message: string;
};

export type SyncCompleteEvent = {
  success: boolean;
  integration?: Integration;
  stats?: { added: number; total: number; last_synced: string };
};

export type SyncCallbacks = {
  onProgress?: (event: SyncProgressEvent) => void;
  onComplete?: (event: SyncCompleteEvent) => void;
  onError?: (message: string) => void;
};

export const syncIntegration = async (
  integrationId: string,
  callbacks?: SyncCallbacks
): Promise<Integration | null> => {
  const token = localStorage.getItem("token");
  try {
    const response = await fetch(`${BE_URL}/integrations/sync/${integrationId}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });

    if (!response.ok || !response.body) {
      callbacks?.onError?.(`Sync failed: ${response.statusText}`);
      return null;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let finalIntegration: Integration | null = null;
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Parse SSE events from buffer
      const lines = buffer.split("\n");
      buffer = lines.pop() || ""; // keep incomplete line in buffer

      let eventType = "";
      for (const line of lines) {
        if (line.startsWith("event: ")) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          const jsonStr = line.slice(6);
          try {
            const data = JSON.parse(jsonStr);
            if (eventType === "progress") {
              callbacks?.onProgress?.(data as SyncProgressEvent);
            } else if (eventType === "complete") {
              const completeData = data as SyncCompleteEvent;
              callbacks?.onComplete?.(completeData);
              finalIntegration = completeData.integration || null;
            } else if (eventType === "error") {
              callbacks?.onError?.(data.message || "Unknown sync error");
            }
          } catch {
            // skip malformed JSON
          }
          eventType = "";
        }
      }
    }

    return finalIntegration;
  } catch (error) {
    logger.error("Error syncing integration:", error);
    callbacks?.onError?.(error instanceof Error ? error.message : "Sync failed");
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

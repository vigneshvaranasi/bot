import http from "../utils/http";
import { logger } from "../utils/logger";
import type {
  ModelRoutingConfigListResponse,
  BulkUpsertItem,
  RoutingMetadataResponse,
} from "../types/ModelRouting";

export const fetchRoutingConfigs = async (): Promise<ModelRoutingConfigListResponse | null> => {
  try {
    const { data } = await http.get("/model-routing/");
    return data;
  } catch (error) {
    logger.error("Error fetching routing configs:", error);
    return null;
  }
};

export const bulkUpsertRoutingConfigs = async (
  configs: BulkUpsertItem[]
): Promise<ModelRoutingConfigListResponse | null> => {
  try {
    const { data } = await http.post("/model-routing/bulk", { configs });
    return data;
  } catch (error) {
    logger.error("Error saving routing configs:", error);
    return null;
  }
};

export const deleteRoutingConfig = async (configId: string): Promise<boolean> => {
  try {
    await http.delete(`/model-routing/${configId}`);
    return true;
  } catch (error) {
    logger.error("Error deleting routing config:", error);
    return false;
  }
};

export const fetchTaskTypes = async (): Promise<string[]> => {
  try {
    const { data } = await http.get("/model-routing/task-types");
    return data;
  } catch (error) {
    logger.error("Error fetching task types:", error);
    return [];
  }
};

export const fetchRoutingMetadata = async (): Promise<RoutingMetadataResponse | null> => {
  try {
    const { data } = await http.get("/model-routing/metadata");
    return data;
  } catch (error) {
    logger.error("Error fetching routing metadata:", error);
    return null;
  }
};
// Knowledge Base API handlers
import http from "../utils/http";
import { logger } from "../utils/logger";

export interface Incident {
  incident_id: string;
  title: string;
  description: string;
  action_taken: string;
  opened_at?: string;
  updated_at?: string;
  source: string;
}

export interface IncidentLog {
  id: string;
  incident_id: string;
  title: string;
  source: string;
  created_at: string;
}

export async function fetchIncidents(): Promise<Incident[] | null> {
  try {
    const { data } = await http.get("/api/knowledge-base/incidents");
    if (data.success) {
      return data.incidents;
    }
    return null;
  } catch (error) {
    logger.error("Error fetching incidents:", error);
    return null;
  }
}

export async function deleteIncident(incidentId: string): Promise<boolean> {
  try {
    const { data } = await http.delete(`/api/knowledge-base/incidents/${encodeURIComponent(incidentId)}`);
    return data.success;
  } catch (error) {
    logger.error("Error deleting incident:", error);
    return false;
  }
}

export async function fetchIncidentLogs(limit: number = 10): Promise<IncidentLog[] | null> {
  try {
    const { data } = await http.get(`/api/knowledge-base/logs?limit=${limit}`);
    if (data.success) {
      return data.logs;
    }
    return null;
  } catch (error) {
    logger.error("Error fetching incident logs:", error);
    return null;
  }
}

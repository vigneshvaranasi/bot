import http from "../utils/http";
import { logger } from "../utils/logger";
import { BE_URL } from "../config/config";
import type { DatasetVersionList, ValidationReport } from "../types/KnowledgeBase";

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

// ── Upload & Validation ─────────────────────────────────────────

export interface UploadResult {
  session_id: string;
  status: string;
  incident_count: number;
  file_metadata: { filename: string; size: number; content_type: string; row_count: number }[];
  preview: Record<string, unknown>[];
}

export async function uploadIncidentFiles(
  files: { filename: string; size: number; content: string }[]
): Promise<UploadResult | null> {
  try {
    const { data } = await http.post("/api/knowledge-base/upload", { files });
    if (data.success) {
      return data as UploadResult;
    }
    return null;
  } catch (error) {
    logger.error("Error uploading incident files:", error);
    return null;
  }
}

export async function validateUploadSession(sessionId: string): Promise<ValidationReport | null> {
  try {
    const { data } = await http.post(`/api/knowledge-base/validate/${sessionId}`);
    if (data.success) {
      return data as ValidationReport;
    }
    return null;
  } catch (error) {
    logger.error("Error validating upload session:", error);
    return null;
  }
}

export async function applyFieldMapping(
  sessionId: string,
  mapping: Record<string, string>
): Promise<ValidationReport | null> {
  try {
    const { data } = await http.post(`/api/knowledge-base/validate/${sessionId}/map-fields`, {
      session_id: sessionId,
      mapping,
    });
    if (data.success) {
      return data as ValidationReport;
    }
    return null;
  } catch (error) {
    logger.error("Error applying field mapping:", error);
    return null;
  }
}

// ── Ingestion (SSE) ─────────────────────────────────────────────

export function startIngestion(
  sessionId: string,
  notes: string | undefined,
  onProgress: (data: Record<string, unknown>) => void,
  onComplete: (data: Record<string, unknown>) => void,
  onError: (message: string) => void
): AbortController {
  const controller = new AbortController();
  const token = localStorage.getItem("token");

  fetch(`${BE_URL}/api/knowledge-base/ingest`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ session_id: sessionId, notes }),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok || !response.body) {
        onError(`Request failed (HTTP ${response.status}). Please try again.`);
        return;
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        let eventType = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            try {
              const parsed = JSON.parse(line.slice(6));
              if (eventType === "progress") onProgress(parsed);
              else if (eventType === "complete") onComplete(parsed);
              else if (eventType === "error") onError(parsed.message || "Unknown error");
            } catch {
              // skip unparseable lines
            }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        onError("A network error occurred. Please check your connection and try again.");
        logger.error("Ingestion network error:", err);
      }
    });

  return controller;
}

// ── Version Management ──────────────────────────────────────────

export async function fetchDatasetVersions(
  limit = 20,
  offset = 0
): Promise<DatasetVersionList | null> {
  try {
    const { data } = await http.get(`/api/knowledge-base/versions?limit=${limit}&offset=${offset}`);
    if (data.success) {
      return { versions: data.versions, total: data.total, active_version_id: data.active_version_id };
    }
    return null;
  } catch (error) {
    logger.error("Error fetching dataset versions:", error);
    return null;
  }
}

export async function rollbackToVersion(
  versionId: string,
  notes?: string
): Promise<{ success: boolean; error?: string }> {
  try {
    const { data } = await http.post(`/api/knowledge-base/versions/${versionId}/rollback`, {
      notes: notes || null,
    });
    return { success: !!data.success };
  } catch (error: unknown) {
    const msg =
      error instanceof Error ? error.message : "Unknown error rolling back version";
    logger.error("Error rolling back version:", error);
    return { success: false, error: msg };
  }
}

export async function deleteVersion(
  versionId: string
): Promise<{ success: boolean; error?: string }> {
  try {
    const { data } = await http.delete(`/api/knowledge-base/versions/${versionId}`);
    return { success: !!data.success };
  } catch (error: unknown) {
    const msg =
      error instanceof Error ? error.message : "Unknown error deleting version";
    logger.error("Error deleting version:", error);
    return { success: false, error: msg };
  }
}

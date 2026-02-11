import { useCallback, useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import SettingsHeader from "../../components/settings/SettingsHeader";
import { Button } from "../../components/ui/Button";
import UploadFiles from "../../components/ui/UploadFiles";
import { ConfigurableTable } from "../../components/ui/Table";
import { SkeletonAudit } from "../../components/ui/Skeleton";
import { usePermissions } from "../../hooks/usePermissions";
import InfoHint from "../../components/ui/InfoHint";
import { useFileContext } from "../../hooks/useFileContext";
import { PERMISSIONS } from "../../types/Permission";
import type { ValidationReport } from "../../types/KnowledgeBase";
import {
  fetchIntegrations,
} from "../../handlers/integrationHandlers";
import {
  fetchIncidentLogs,
  uploadIncidentFiles,
  validateUploadSession,
  applyFieldMapping,
  startIngestion,
  type IncidentLog,
  type UploadResult,
} from "../../handlers/knowledgeBaseHandlers";
import type { Integration } from "../../types/Integrations";

import ValidationReportPanel from "../../components/knowledge-base/ValidationReportPanel";
import FieldMappingPanel from "../../components/knowledge-base/FieldMappingPanel";
import IngestionProgressBar from "../../components/knowledge-base/IngestionProgressBar";
import VersionListPanel from "../../components/knowledge-base/VersionListPanel";

// ── Tab definitions ─────────────────────────────────────────────

type TabId = "upload" | "versions" | "sync";

const TABS: { id: TabId; label: string; permission?: string }[] = [
  { id: "upload", label: "Upload & Ingest", permission: PERMISSIONS.KB_UPLOAD },
  { id: "versions", label: "Versions", permission: PERMISSIONS.KB_VIEW },
  { id: "sync", label: "Sync History", permission: PERMISSIONS.KB_VIEW },
];

// ── Upload flow state machine ───────────────────────────────────

type UploadStep = "upload" | "preview" | "validate" | "mapping" | "ingest" | "done";

// ── Page component ──────────────────────────────────────────────

const KnowledgeBasePage = () => {
  const { hasPermission, loading: permLoading } = usePermissions();
  const { files: contextFiles, clearAllFiles } = useFileContext();
  const [activeTab, setActiveTab] = useState<TabId>("upload");

  // Sync History tab state (existing)
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [logs, setLogs] = useState<IncidentLog[]>([]);
  const [syncLoading, setSyncLoading] = useState(true);

  // Upload tab state
  const [step, setStep] = useState<UploadStep>("upload");
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [uploadLoading, setUploadLoading] = useState(false);

  // Ingestion progress
  const [ingBatch, setIngBatch] = useState(0);
  const [ingTotal, setIngTotal] = useState(0);
  const [ingMsg, setIngMsg] = useState("");
  const [ingComplete, setIngComplete] = useState(false);
  const [ingError, setIngError] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  // Track whether we've already triggered upload for the current context files
  const uploadTriggeredRef = useRef(false);

  // Clear stale files from context on mount / unmount
  useEffect(() => {
    clearAllFiles();
    return () => { clearAllFiles(); };
  }, []);

  // When UploadFiles pushes files to context via "Process Files", trigger upload
  useEffect(() => {
    if (contextFiles.length > 0 && step === "upload" && !uploadTriggeredRef.current) {
      uploadTriggeredRef.current = true;
      handleUpload();
    }
  }, [contextFiles, step]);

  // Reset trigger when context is cleared
  useEffect(() => {
    if (contextFiles.length === 0) {
      uploadTriggeredRef.current = false;
    }
  }, [contextFiles]);

  // ── Sync tab loader ───────────────────────────────────────────

  const loadSyncData = async () => {
    setSyncLoading(true);
    const result = await fetchIntegrations();
    if (result) {
      setIntegrations(result.filter((i) => i.service_name === "snow" && i.last_synced_at));
    }
    const logsResult = await fetchIncidentLogs(50);
    if (logsResult) setLogs(logsResult);
    setSyncLoading(false);
  };

  useEffect(() => {
    if (activeTab === "sync") loadSyncData();
  }, [activeTab]);

  // ── Upload handlers ───────────────────────────────────────────

  const handleUpload = useCallback(async () => {
    if (contextFiles.length === 0) return;
    setUploadLoading(true);

    const filesData = contextFiles.map((f) => ({
      filename: f.name,
      size: f.size,
      content: f.content || "",
    }));

    const result = await uploadIncidentFiles(filesData);
    setUploadLoading(false);

    if (result) {
      setUploadResult(result);
      setStep("preview");
    } else {
      toast.error("Upload failed");
      uploadTriggeredRef.current = false; // allow retry
    }
  }, [contextFiles]);

  const handleValidate = async () => {
    if (!uploadResult) return;
    setUploadLoading(true);
    const r = await validateUploadSession(uploadResult.session_id);
    setUploadLoading(false);
    if (r) {
      setReport(r);
      setStep("validate");
    } else {
      toast.error("Validation failed");
    }
  };

  const handleMapFieldsApply = async (mapping: Record<string, string>) => {
    if (!uploadResult) return;
    setUploadLoading(true);
    const r = await applyFieldMapping(uploadResult.session_id, mapping);
    setUploadLoading(false);
    if (r) {
      setReport(r);
      setStep("validate");
    } else {
      toast.error("Field mapping failed");
    }
  };

  const handleConfirmIngest = () => {
    if (!uploadResult) return;
    setStep("ingest");
    setIngBatch(0);
    setIngTotal(0);
    setIngMsg("Starting...");
    setIngComplete(false);
    setIngError(false);

    const ctrl = startIngestion(
      uploadResult.session_id,
      undefined,
      (data) => {
        setIngBatch((data.batch as number) || 0);
        setIngTotal((data.totalBatches as number) || 0);
        setIngMsg((data.message as string) || "");
      },
      (data) => {
        setIngComplete(true);
        const count = (data.incident_count as number) || 0;
        setIngMsg(`Ingestion complete! Version v${data.version_number} activated with ${count} total incidents.`);
        toast.success("Incidents ingested and version activated");
      },
      (msg) => {
        setIngError(true);
        setIngMsg(msg);
        toast.error(`Ingestion error: ${msg}`);
      }
    );
    abortRef.current = ctrl;
  };

  const resetUpload = () => {
    setStep("upload");
    setUploadResult(null);
    setReport(null);
    clearAllFiles();
    setIngComplete(false);
    setIngError(false);
  };

  // ── Render helpers ────────────────────────────────────────────

  const visibleTabs = TABS.filter(
    (t) => !t.permission || hasPermission(t.permission)
  );

  if (permLoading) {
    return (
      <div className="space-y-6">
        <SettingsHeader title="Knowledge Base" description="Manage incident data" />
        <SkeletonAudit />
      </div>
    );
  }

  // ── Sync history columns (existing) ────────────────────────────

  const syncColumns = [
    {
      header: "Source",
      headerClassName: "font-medium text-gray-700 text-xs md:text-sm sticky top-0 bg-gray-50 z-10 border-b border-gray-200",
      className: "text-xs md:text-sm py-3",
      render: (item: Integration) => (
        <span className="font-medium capitalize">
          {item.service_name === "snow" ? "ServiceNow" : item.service_name}
        </span>
      ),
      searchable: false,
    },
    {
      header: "Last Synced",
      headerClassName: "font-medium text-gray-700 text-xs md:text-sm sticky top-0 bg-gray-50 z-10 border-b border-gray-200",
      className: "text-xs md:text-sm py-3",
      render: (item: Integration) =>
        item.last_synced_at ? new Date(item.last_synced_at).toLocaleString() : "Never",
      searchable: false,
    },
    {
      header: "Status",
      headerClassName: "font-medium text-gray-700 text-xs md:text-sm sticky top-0 bg-gray-50 z-10 border-b border-gray-200",
      className: "text-xs md:text-sm py-3",
      render: (item: Integration) => {
        const status = item.last_sync_status || "never";
        const colors: Record<string, string> = {
          success: "bg-green-100 text-green-800",
          error: "bg-red-100 text-red-800",
          never: "bg-gray-100 text-gray-800",
        };
        return (
          <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${colors[status] || colors.never}`}>
            {status.charAt(0).toUpperCase() + status.slice(1)}
          </span>
        );
      },
      searchable: false,
    },
    {
      header: "Updated",
      headerClassName: "font-medium text-gray-700 text-xs md:text-sm sticky top-0 bg-gray-50 z-10 border-b border-gray-200",
      className: "text-xs md:text-sm py-3",
      render: (item: Integration) =>
        item.updated_at ? new Date(item.updated_at).toLocaleString() : "-",
      searchable: false,
    },
  ];

  return (
    <div className="space-y-6">
      <SettingsHeader
        title="Knowledge Base"
        description="Upload incident data, manage dataset versions, and view sync history"
      />

      {/* Tab bar */}
      <div className="border-b border-gray-200">
        <nav className="flex -mb-px space-x-6">
          {visibleTabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-blue-500 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* ── Upload & Ingest Tab ──────────────────────────────── */}
      {activeTab === "upload" && (
        <div className="space-y-4">
          {step === "upload" && (
            <div className="space-y-3">
              <div className="flex items-center gap-1">
                <p className="text-sm text-gray-600">
                  Upload JSON or CSV files containing incident data. Required fields: incident_id, title, description.
                </p>
                <InfoHint text="Upload a JSON array of objects or a CSV with headers. Each record needs at least: incident_id, title, and description. Optional fields like action_taken and priority are also supported." />
              </div>
              <UploadFiles compact supportedFileTypes={[".json", ".csv"]} />
              {uploadLoading && (
                <div className="flex items-center gap-2 text-xs text-gray-500 px-1">
                  <svg className="animate-spin h-4 w-4 text-blue-500" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Uploading and parsing files...
                </div>
              )}
            </div>
          )}

          {step === "preview" && uploadResult && (
            <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
              <h3 className="text-sm font-medium text-gray-900">Upload Preview</h3>
              <div className="flex gap-4 text-xs text-gray-600">
                <span>{uploadResult.incident_count} records parsed</span>
                <span>{uploadResult.file_metadata.length} file(s)</span>
              </div>
              {uploadResult.file_metadata.map((fm, i) => (
                <div key={i} className="flex items-center gap-3 py-2 px-3 bg-gray-50 rounded border border-gray-200 text-xs">
                  <span className="font-medium">{fm.filename}</span>
                  <span className="text-gray-500">{(fm.size / 1024).toFixed(1)} KB</span>
                  <span className="text-gray-500">{fm.row_count} rows</span>
                </div>
              ))}
              <div className="flex justify-end gap-2">
                <Button variant="secondary" onClick={resetUpload} className="text-xs">
                  Cancel
                </Button>
                <Button variant="primary" onClick={handleValidate} disabled={uploadLoading} className="text-xs">
                  {uploadLoading ? "Validating..." : "Validate"}
                </Button>
              </div>
            </div>
          )}

          {step === "validate" && report && (
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h3 className="text-sm font-medium text-gray-900 mb-4">Validation Report</h3>
              <ValidationReportPanel
                report={report}
                onMapFields={() => setStep("mapping")}
                onConfirmIngest={handleConfirmIngest}
              />
            </div>
          )}

          {step === "mapping" && report && (
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h3 className="text-sm font-medium text-gray-900 mb-4">Field Mapping</h3>
              <FieldMappingPanel
                fileFields={report.file_fields || {}}
                onApply={handleMapFieldsApply}
                onCancel={() => setStep("validate")}
                isLoading={uploadLoading}
              />
            </div>
          )}

          {step === "ingest" && (
            <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
              <h3 className="text-sm font-medium text-gray-900">Ingestion Progress</h3>
              <IngestionProgressBar
                batch={ingBatch}
                totalBatches={ingTotal}
                message={ingMsg}
                isComplete={ingComplete}
                isError={ingError}
              />
              {(ingComplete || ingError) && (
                <div className="flex justify-end">
                  <Button variant="primary" onClick={resetUpload} className="text-xs">
                    Upload Another
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Versions Tab ─────────────────────────────────────── */}
      {activeTab === "versions" && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-sm font-medium text-gray-900 mb-4">Dataset Versions</h3>
          <VersionListPanel />
        </div>
      )}

      {/* ── Sync History Tab (existing content) ──────────────── */}
      {activeTab === "sync" && (
        <>
          {syncLoading ? (
            <SkeletonAudit />
          ) : (
            <>
              {/* Incident Logs */}
              {logs.length > 0 && (
                <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
                  <div className="p-4 border-b border-gray-200 flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-medium text-gray-900">Recent Incidents</h3>
                      <p className="text-xs text-gray-500 mt-1">
                        Log of incidents added to the knowledge base
                      </p>
                    </div>
                    <Button onClick={loadSyncData} variant="secondary" className="text-xs px-3 py-1">
                      Refresh
                    </Button>
                  </div>
                  <div className="max-h-[300px] overflow-y-auto">
                    <div className="divide-y divide-gray-100">
                      {logs.slice(0, 50).map((log) => (
                        <div key={log.id} className="p-3 hover:bg-gray-50 transition-colors">
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-mono text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                                  {log.incident_id}
                                </span>
                                <span className="text-xs text-gray-500 bg-blue-50 px-2 py-0.5 rounded capitalize">
                                  {log.source}
                                </span>
                              </div>
                              <p className="text-sm text-gray-900 mt-1 truncate" title={log.title}>
                                {log.title}
                              </p>
                            </div>
                            <div className="text-xs text-gray-500 whitespace-nowrap">
                              {new Date(log.created_at).toLocaleString()}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Sync History Table */}
              <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
                <div className="p-4 border-b border-gray-200 flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-medium text-gray-900">Sync History</h3>
                    <p className="text-xs text-gray-500 mt-1">
                      Incidents are automatically synced to the vector database when integrations are updated
                    </p>
                  </div>
                  <Button onClick={loadSyncData} variant="secondary" className="text-xs px-3 py-1">
                    Refresh
                  </Button>
                </div>
                {integrations.length === 0 ? (
                  <div className="p-8 text-center">
                    <p className="text-sm text-gray-500">
                      No sync history available. Configure a ServiceNow integration in{" "}
                      <a href="/settings/integrations" className="text-blue-600 hover:underline">
                        Integrations
                      </a>{" "}
                      and click "Sync Now" to populate the knowledge base.
                    </p>
                  </div>
                ) : (
                  <ConfigurableTable data={integrations} columns={syncColumns} />
                )}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
};

export default KnowledgeBasePage;

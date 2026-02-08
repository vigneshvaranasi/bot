import { useEffect, useState } from "react";
import SettingsHeader from "../../components/settings/SettingsHeader";
import { Button } from "../../components/ui/Button";
import { ConfigurableTable } from "../../components/ui/Table";
import { ConfirmModal } from "../../components/ui/Modal";
import { fetchSettingsHistory, rollbackToVersion } from "../../handlers/settingsHandlers";
import type { SettingHistoryItem } from "../../types/Settings";
import { toast } from "react-hot-toast";
import { logger } from "../../utils/logger";
import { SkeletonAudit } from "../../components/ui/Skeleton";

const AuditPage = () => {
  const [history, setHistory] = useState<SettingHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rollingBack, setRollingBack] = useState<string | null>(null);
  const [total, setTotal] = useState(0);

  // Rollback confirmation modal state
  const [rollbackModalOpen, setRollbackModalOpen] = useState(false);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetchSettingsHistory(50, 0);
      if (response) {
        setHistory(response.history);
        setTotal(response.total);
      } else {
        setError("Unable to load settings history");
      }
    } catch (err) {
      logger.error("Error fetching settings history", err);
      setError("Failed to load settings history");
    } finally {
      setLoading(false);
    }
  };

  const openRollbackModal = (versionId: string) => {
    setSelectedVersionId(versionId);
    setRollbackModalOpen(true);
  };

  const handleConfirmRollback = async () => {
    if (!selectedVersionId) return;

    try {
      setRollingBack(selectedVersionId);
      setRollbackModalOpen(false);
      const result = await rollbackToVersion(selectedVersionId);
      if (result) {
        toast.success("Settings rolled back successfully");
        await loadHistory(); // Reload history to show new version
      } else {
        toast.error("Failed to rollback settings");
      }
    } catch (err) {
      logger.error("Error rolling back settings", err);
      toast.error("Failed to rollback settings");
    } finally {
      setRollingBack(null);
      setSelectedVersionId(null);
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString();
  };

  const truncateText = (text: string, maxLength: number = 30) => {
    if (!text) return "-";
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + "...";
  };

  if (loading && history.length === 0) {
    return (
      <div className="space-y-6">
        <SettingsHeader
          title="Audit & Logs"
          description="Review configuration change history and rollback to previous versions."
        />
        <SkeletonAudit />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <SettingsHeader
        title="Audit & Logs"
        description="Review configuration change history and rollback to previous versions."
      />

      {error ? (
        <div className="p-3 bg-red-50 text-sm text-red-700 border border-red-200 rounded">
          {error}
        </div>
      ) : null}

      <section className="border border-gray-200 rounded-lg p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Settings History</h3>
            <p className="text-xs text-gray-600">
              {total > 0 ? `${total} version(s) recorded` : "No settings history available"}
            </p>
          </div>
          <Button variant="secondary" onClick={loadHistory} disabled={loading}>
            {loading ? "Refreshing…" : "Refresh"}
          </Button>
        </div>

        {!loading && history.length === 0 ? (
          <div className="p-6 text-center text-gray-500 text-sm border border-dashed border-gray-300 rounded-lg bg-gray-50">
            No settings history available. Changes to settings will appear here.
          </div>
        ) : null}

        {history.length > 0 ? (
          <div className="overflow-x-auto bg-white rounded-lg border border-gray-300">
            <div className="max-h-96 overflow-y-auto">
              <ConfigurableTable
                data={history}
                keyExtractor={(row) => row.id}
                columns={[
                  {
                    header: "Date",
                    headerClassName: "font-medium text-gray-700 text-xs md:text-sm sticky top-0 bg-gray-50 z-10 border-b border-gray-200 min-w-[140px]",
                    className: "text-xs md:text-sm text-gray-900 py-3",
                    render: (item) => formatDate(item.updated_at),
                    searchable: false,
                  },
                  {
                    header: "Model",
                    accessor: "model",
                    headerClassName: "font-medium text-gray-700 text-xs md:text-sm sticky top-0 bg-gray-50 z-10 border-b border-gray-200",
                    className: "text-xs md:text-sm text-gray-900 py-3",
                    searchable: true,
                  },
                  {
                    header: "Temp",
                    accessor: "temperature",
                    headerClassName: "font-medium text-gray-700 text-xs md:text-sm sticky top-0 bg-gray-50 z-10 border-b border-gray-200 w-16",
                    className: "text-xs md:text-sm text-gray-900 py-3",
                    searchable: false,
                  },
                  {
                    header: "Langfuse",
                    headerClassName: "font-medium text-gray-700 text-xs md:text-sm sticky top-0 bg-gray-50 z-10 border-b border-gray-200 w-20",
                    className: "text-xs md:text-sm py-3",
                    render: (item) => (
                      <span className={item.langfuse_enabled ? "text-green-600" : "text-gray-400"}>
                        {item.langfuse_enabled ? "On" : "Off"}
                      </span>
                    ),
                    searchable: false,
                  },
                  {
                    header: "Auth Providers",
                    headerClassName: "font-medium text-gray-700 text-xs md:text-sm sticky top-0 bg-gray-50 z-10 border-b border-gray-200 min-w-[120px]",
                    className: "text-xs md:text-sm text-gray-900 py-3",
                    render: (item) => {
                      const providers = [];
                      if (item.auth_google_enabled) providers.push("G");
                      if (item.auth_github_enabled) providers.push("GH");
                      if (item.auth_microsoft_enabled) providers.push("MS");
                      if (item.auth_local_enabled) providers.push("L");
                      return providers.length > 0 ? providers.join(", ") : "-";
                    },
                    searchable: false,
                  },
                  {
                    header: "Deny Words",
                    headerClassName: "font-medium text-gray-700 text-xs md:text-sm sticky top-0 bg-gray-50 z-10 border-b border-gray-200",
                    className: "text-xs md:text-sm text-gray-500 py-3",
                    render: (item) => (
                      <span title={item.deny_words || ""}>
                        {truncateText(item.deny_words, 20)}
                      </span>
                    ),
                    searchable: false,
                  },
                  {
                    header: "Action",
                    headerClassName: "font-medium text-gray-700 text-xs md:text-sm sticky top-0 bg-gray-50 z-10 border-b border-gray-200 w-24",
                    render: (item, index) => (
                      <Button
                        variant="secondary"
                        className={`text-xs px-2 py-1 ${
                          index === 0
                            ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                            : "bg-blue-50 text-blue-600 hover:bg-blue-100"
                        }`}
                        onClick={() => openRollbackModal(item.id)}
                        disabled={index === 0 || rollingBack === item.id}
                      >
                        {rollingBack === item.id ? "..." : index === 0 ? "Current" : "Rollback"}
                      </Button>
                    ),
                    searchable: false,
                  },
                ]}
                headerRowClassName="bg-gray-50 sticky top-0 z-10"
                rowClassName="bg-white border-t border-gray-200 hover:bg-gray-50"
              />
            </div>
          </div>
        ) : null}
      </section>

      <section className="border border-gray-200 rounded-lg p-4 space-y-4">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">Legend</h3>
          <p className="text-xs text-gray-600 mt-1">Auth Provider abbreviations:</p>
        </div>
        <div className="flex flex-wrap gap-4 text-xs text-gray-600">
          <span><strong>G</strong> = Google</span>
          <span><strong>GH</strong> = GitHub</span>
          <span><strong>MS</strong> = Microsoft</span>
          <span><strong>L</strong> = Local (Password)</span>
        </div>
      </section>

      {/* Rollback Confirmation Modal */}
      <ConfirmModal
        isOpen={rollbackModalOpen}
        onClose={() => {
          setRollbackModalOpen(false);
          setSelectedVersionId(null);
        }}
        onConfirm={handleConfirmRollback}
        title="Rollback Settings"
        message="Are you sure you want to rollback to this version? This will create a new settings version with these values."
        confirmLabel="Rollback"
        cancelLabel="Cancel"
        confirmVariant="primary"
        isLoading={!!rollingBack}
      />
    </div>
  );
};

export default AuditPage;

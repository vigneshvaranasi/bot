import { useEffect, useState, useCallback } from "react";
import SettingsHeader from "../../components/settings/SettingsHeader";
import { Button } from "../../components/ui/Button";
import { ConfigurableTable } from "../../components/ui/Table";
import Dropdown from "../../components/ui/Dropdown";
import Modal, { InputModal } from "../../components/ui/Modal";
import { fetchSettingsHistory, rollbackToVersion } from "../../handlers/settingsHandlers";
import type { SettingHistoryItem, SettingSegment, ChangeType, ChangeDescription } from "../../types/Settings";
import { toast } from "react-hot-toast";
import { logger } from "../../utils/logger";
import { SkeletonAudit } from "../../components/ui/Skeleton";
import { Pagination, DEFAULT_PAGE_SIZE_OPTIONS } from "../../components/ui/Pagination";
import { useDelayedLoading } from "../../hooks/useDelayedLoading";
import { usePermissions } from "../../hooks/usePermissions";
import { PERMISSIONS } from "../../types/Permission";
import InfoHint from "../../components/ui/InfoHint";

const DEFAULT_PAGE_SIZE = 15;

// Change type badge colors
const CHANGE_TYPE_COLORS: Record<ChangeType, string> = {
  create: "bg-success-subtle text-success-text",
  update: "bg-info-subtle text-info-text",
  rollback: "bg-warning-subtle text-warning-text",
};

const CHANGE_TYPE_LABELS: Record<ChangeType, string> = {
  create: "Created",
  update: "Updated",
  rollback: "Rollback",
};

// Segment filter options
const SEGMENT_OPTIONS = [
  { value: "", label: "All Changes" },
  { value: "aiml", label: "AI/ML Only" },
  { value: "auth", label: "Auth Only" },
];

// Format version ID for display (show first 8 chars)
const formatVersionId = (id: string): string => {
  return id.substring(0, 8);
};

// Component to display change chips
const ChangeBadges = ({ changes }: { changes: ChangeDescription[] }) => {
  if (changes.length === 0) {
    return <span className="text-text-tertiary text-xs">No changes</span>;
  }

  // Group by segment for better display
  const aimlChanges = changes.filter((c) => c.segment === "aiml");
  const authChanges = changes.filter((c) => c.segment === "auth");

  return (
    <div className="flex flex-row flex-wrap items-center gap-1">
      {aimlChanges.map((change) => (
        <span
          key={change.field}
          className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-surface-tertiary text-text-primary border border-border-default"
          title={`${change.old_value} → ${change.new_value}`}
        >
          {change.field_label}
        </span>
      ))}
      {authChanges.map((change) => (
        <span
          key={change.field}
          className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-info-subtle text-info-text border border-info-border"
          title={`${change.old_value} → ${change.new_value}`}
        >
          {change.field_label}
        </span>
      ))}
    </div>
  );
};

const ConfigurationHistoryPage = () => {
  const { hasPermission } = usePermissions();
  const canRollback = hasPermission(PERMISSIONS.HISTORY_ROLLBACK);

  const [history, setHistory] = useState<SettingHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rollingBack, setRollingBack] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [segmentFilter, setSegmentFilter] = useState<SettingSegment | "">("");

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);

  // Delayed loading - only show skeleton after 150ms
  const showLoading = useDelayedLoading(loading);
  // Track if we've loaded data at least once (for initial load skeleton)
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);

  // Modal state
  const [rollbackModalOpen, setRollbackModalOpen] = useState(false);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);

  // Detail modal state
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [selectedItem, setSelectedItem] = useState<SettingHistoryItem | null>(null);

  const loadHistory = useCallback(async (page: number, size: number, segment?: SettingSegment) => {
    try {
      setLoading(true);
      setError(null);
      const offset = (page - 1) * size;
      const response = await fetchSettingsHistory(
        size,
        offset,
        segment || undefined
      );
      if (response) {
        setHistory(response.history);
        setTotal(response.total);
      } else {
        setError("Unable to load configuration history");
      }
    } catch (err) {
      logger.error("Error fetching configuration history", err);
      setError("Failed to load configuration history");
    } finally {
      setLoading(false);
      setHasLoadedOnce(true);
    }
  }, []);

  useEffect(() => {
    setCurrentPage(1);
    loadHistory(1, pageSize, segmentFilter || undefined);
  }, [segmentFilter, pageSize, loadHistory]);

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    loadHistory(page, pageSize, segmentFilter || undefined);
  };

  const handlePageSizeChange = (size: number) => {
    setPageSize(size);
    setCurrentPage(1); // Reset to page 1 when changing page size
  };

  const handleRefresh = () => {
    loadHistory(currentPage, pageSize, segmentFilter || undefined);
  };

  const totalPages = Math.ceil(total / pageSize);

  const openRollbackModal = (versionId: string) => {
    setSelectedVersionId(versionId);
    setRollbackModalOpen(true);
  };

  const handleRollback = async (reason: string) => {
    if (!selectedVersionId) return;

    try {
      setRollingBack(selectedVersionId);
      setRollbackModalOpen(false);

      const result = await rollbackToVersion(selectedVersionId, reason || undefined);
      if (result) {
        toast.success("Configuration rolled back successfully");
        // Go back to page 1 to see the new rollback entry
        setCurrentPage(1);
        await loadHistory(1, pageSize, segmentFilter || undefined);
      } else {
        toast.error("Failed to rollback configuration");
      }
    } catch (err) {
      logger.error("Error rolling back configuration", err);
      toast.error("Failed to rollback configuration");
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

  // Show skeleton only on initial load when delayed threshold is met
  if (showLoading && !hasLoadedOnce) {
    return (
      <div className="space-y-6">
        <SettingsHeader
          title="Configuration History"
          description="Review configuration changes, audit trail, and rollback to previous versions."
        />
        <SkeletonAudit />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <SettingsHeader
        title="Configuration History"
        description="Review configuration changes, audit trail, and rollback to previous versions."
      />

      {error && (
        <div className="p-3 bg-danger-subtle text-sm text-danger-text border border-danger rounded">
          {error}
        </div>
      )}

      <section className="border border-border-default rounded-lg p-4 space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h3 className="text-sm font-semibold text-text-primary">Version History</h3>
            <p className="text-xs text-text-secondary">
              {total > 0 ? `${total} version(s) recorded` : "No configuration history available"}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-1">
              <span className="text-xs text-text-secondary">Segment</span>
              <InfoHint text="Filter by area of change. 'AI/ML' shows model, temperature, and deny list changes. 'Auth' shows login provider changes." />
            </div>
            <Dropdown
              options={SEGMENT_OPTIONS}
              value={segmentFilter}
              onChange={(v) => setSegmentFilter((v as SettingSegment) || "")}
              placeholder="Filter by segment"
            />
            <Button variant="secondary" size="sm" onClick={handleRefresh} disabled={loading}>
              {loading ? "Refreshing..." : "Refresh"}
            </Button>
          </div>
        </div>

        {!loading && history.length === 0 && (
          <div className="p-6 text-center text-text-secondary text-sm border border-dashed border-border-strong rounded-lg bg-surface-secondary">
            No configuration history available. Changes to settings will appear here.
          </div>
        )}

        {history.length > 0 && (
          <>
            <div className="overflow-x-auto bg-surface-primary rounded-lg ">
              <div className="max-h-[400px] overflow-y-auto">
                <ConfigurableTable
                  data={history}
                  keyExtractor={(row) => row.id}
                  columns={[
                    {
                      header: "Version",
                      headerClassName:
                        "font-medium text-text-secondary text-xs md:text-sm sticky top-0 bg-surface-secondary z-10 border-b border-border-default min-w-[90px]",
                      className: "text-xs md:text-sm text-text-primary py-3 font-mono",
                      render: (item) => {
                        // Only show "Current" badge on page 1, first item
                        const isCurrentVersion = currentPage === 1 && history[0]?.id === item.id;
                        return (
                          <div className="flex items-center gap-2">
                            <span title={item.id}>{formatVersionId(item.id)}</span>
                            {isCurrentVersion && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-success-subtle text-success-text">
                                Current
                              </span>
                            )}
                          </div>
                        );
                      },
                      searchable: false,
                    },
                    {
                      header: "Date",
                      headerClassName:
                        "font-medium text-text-secondary text-xs md:text-sm sticky top-0 bg-surface-secondary z-10 border-b border-border-default min-w-[140px]",
                      className: "text-xs md:text-sm text-text-primary py-3",
                      render: (item) => formatDate(item.updated_at),
                      searchable: false,
                    },
                    {
                      header: "Type",
                      headerClassName:
                        "font-medium text-text-secondary text-xs md:text-sm sticky top-0 bg-surface-secondary z-10 border-b border-border-default w-24",
                      className: "text-xs md:text-sm py-3",
                      render: (item) => (
                        <span
                          className={`text-xs px-2 py-1 rounded-full ${CHANGE_TYPE_COLORS[item.change_type]}`}
                        >
                          {CHANGE_TYPE_LABELS[item.change_type]}
                        </span>
                      ),
                      searchable: false,
                    },
                    {
                      header: "Changed By",
                      headerClassName:
                        "font-medium text-text-secondary text-xs md:text-sm sticky top-0 bg-surface-secondary z-10 border-b border-border-default min-w-[150px]",
                      className: "text-xs md:text-sm text-text-secondary py-3",
                      render: (item) => item.user_email || "Unknown",
                      searchable: true,
                    },
                    {
                      header: "Changes",
                      headerClassName:
                        "font-medium text-text-secondary text-xs md:text-sm sticky top-0 bg-surface-secondary z-10 border-b border-border-default min-w-[150px]",
                      className: "text-xs md:text-sm py-3",
                      render: (item) => (
                        <div>
                          <ChangeBadges changes={item.changes} />
                          {item.change_type === "rollback" && item.target_version_id && (
                            <div className="text-[10px] text-warning-text mt-1">
                              Restored from: {formatVersionId(item.target_version_id)}
                            </div>
                          )}
                        </div>
                      ),
                      searchable: false,
                    },
                    {
                      header: "Actions",
                      headerClassName:
                        "font-medium text-text-secondary text-xs md:text-sm sticky top-0 bg-surface-secondary z-10 border-b border-border-default w-32",
                      render: (item, index) => {
                        // Disable rollback only for the very first item on page 1 (current version)
                        const isCurrentVersion = currentPage === 1 && index === 0;
                        return (
                          <div className="flex items-center gap-2">
                            {canRollback && (
                              <Button
                                variant={isCurrentVersion ? "secondary" : "ghost"}
                                size="sm"
                                rounded="lg"
                                className={isCurrentVersion ? "opacity-50 cursor-not-allowed" : ""}
                                onClick={() => openRollbackModal(item.id)}
                                disabled={isCurrentVersion || rollingBack === item.id}
                              >
                                {rollingBack === item.id ? "..." : "Rollback"}
                              </Button>
                            )}
                            <button
                              className="text-xs text-text-secondary hover:text-text-secondary underline"
                              onClick={() => {
                                setSelectedItem(item);
                                setDetailModalOpen(true);
                              }}
                            >
                              Details
                            </button>
                          </div>
                        );
                      },
                      searchable: false,
                    },
                    {
                      header: "Reason",
                      headerClassName:
                        "font-medium text-text-secondary text-xs md:text-sm sticky top-0 bg-surface-secondary z-10 border-b border-border-default min-w-[120px]",
                      className: "text-xs md:text-sm text-text-secondary py-3",
                      render: (item) => (
                        <span title={item.change_reason || ""}>
                          {truncateText(item.change_reason || "-", 25)}
                        </span>
                      ),
                      searchable: false,
                    },
                  ]}
                  headerRowClassName="bg-surface-secondary sticky top-0 z-10"
                  rowClassName="bg-surface-primary border-t border-border-default hover:bg-surface-secondary"
                />
              </div>
            </div>

            {/* Pagination */}
            <Pagination
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={handlePageChange}
              totalItems={total}
              pageSize={pageSize}
              onPageSizeChange={handlePageSizeChange}
              pageSizeOptions={DEFAULT_PAGE_SIZE_OPTIONS}
              disabled={loading}
            />
          </>
        )}
      </section>

      {/* Legend */}
      <section className="hidden border border-border-default rounded-lg p-4 space-y-4">
        <h3 className="text-sm font-semibold text-text-primary">Legend</h3>
        <div className="flex flex-wrap gap-6 text-xs text-text-secondary">
          <div>
            <span className="font-medium">Change Types:</span>
            <div className="flex gap-2 mt-1">
              <span className={`px-2 py-0.5 rounded-full ${CHANGE_TYPE_COLORS.create}`}>Created</span>
              <span className={`px-2 py-0.5 rounded-full ${CHANGE_TYPE_COLORS.update}`}>Updated</span>
              <span className={`px-2 py-0.5 rounded-full ${CHANGE_TYPE_COLORS.rollback}`}>Rollback</span>
            </div>
          </div>
          <div>
            <span className="font-medium">Change Badges:</span>
            <div className="flex gap-2 mt-1">
              <span className="px-1.5 py-0.5 rounded bg-surface-tertiary text-text-primary border border-border-default">AI/ML</span>
              <span className="px-1.5 py-0.5 rounded bg-info-subtle text-info-text border border-info-border">Auth</span>
            </div>
          </div>
          <div>
            <span className="font-medium">Auth Providers:</span>
            <div className="mt-1">
              <strong>G</strong>=Google, <strong>GH</strong>=GitHub, <strong>MS</strong>=Microsoft, <strong>L</strong>=Local
            </div>
          </div>
        </div>
      </section>

      {/* Rollback Modal */}
      <InputModal
        isOpen={rollbackModalOpen}
        onClose={() => {
          setRollbackModalOpen(false);
          setSelectedVersionId(null);
        }}
        onSubmit={handleRollback}
        title="Rollback Configuration"
        label="Reason for rollback (optional)"
        placeholder="e.g., Reverting due to issues with new settings"
        submitLabel="Rollback"
        cancelLabel="Cancel"
        multiline={true}
        required={false}
      />

      {/* Detail Modal */}
      <Modal
        isOpen={detailModalOpen}
        onClose={() => {
          setDetailModalOpen(false);
          setSelectedItem(null);
        }}
        title="Version Details"
        size="lg"
        footer={
          <Button
            variant="secondary"
            onClick={() => {
              setDetailModalOpen(false);
              setSelectedItem(null);
            }}
          >
            Close
          </Button>
        }
      >
        {selectedItem && (
          <div className="space-y-4">
            {/* Version Info */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
              <div>
                <span className="font-medium text-text-secondary">Version ID:</span>
                <p className="font-mono text-text-secondary break-all text-xs mt-1">{selectedItem.id}</p>
              </div>
              <div>
                <span className="font-medium text-text-secondary">Date:</span>
                <p className="text-text-secondary mt-1">{formatDate(selectedItem.updated_at)}</p>
              </div>
              <div>
                <span className="font-medium text-text-secondary">Changed By:</span>
                <p className="text-text-secondary mt-1">{selectedItem.user_email || "Unknown"}</p>
              </div>
              <div>
                <span className="font-medium text-text-secondary">Type:</span>
                <p className="mt-1">
                  <span className={`text-xs px-2 py-1 rounded-full ${CHANGE_TYPE_COLORS[selectedItem.change_type]}`}>
                    {CHANGE_TYPE_LABELS[selectedItem.change_type]}
                  </span>
                </p>
              </div>
            </div>

            {/* Audit Trail */}
            {(selectedItem.source_version_id || selectedItem.target_version_id || selectedItem.change_reason) && (
              <div className="border-t border-border-default pt-4">
                <h4 className="font-medium text-text-secondary text-sm mb-2">Audit Trail</h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
                  {selectedItem.source_version_id && (
                    <div>
                      <span className="text-text-secondary">Replaced Version:</span>
                      <p className="font-mono text-text-secondary text-xs">{selectedItem.source_version_id}</p>
                    </div>
                  )}
                  {selectedItem.target_version_id && (
                    <div>
                      <span className="text-text-secondary">Restored From:</span>
                      <p className="font-mono text-text-secondary text-xs">{selectedItem.target_version_id}</p>
                    </div>
                  )}
                  {selectedItem.change_reason && (
                    <div className="col-span-2">
                      <span className="text-text-secondary">Reason:</span>
                      <p className="text-text-secondary mt-1">{selectedItem.change_reason}</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Changes */}
            {selectedItem.changes.length > 0 && (
              <div className="border-t border-border-default pt-4">
                <h4 className="font-medium text-text-secondary text-sm mb-2">Changes Made</h4>
                <div className="space-y-2">
                  {selectedItem.changes.map((change) => (
                    <div key={change.field} className="flex items-center gap-2 text-sm">
                      <span
                        className={`px-1.5 py-0.5 rounded text-xs ${
                          change.segment === "aiml"
                            ? "bg-surface-tertiary text-text-primary border border-border-default"
                            : "bg-info-subtle text-info-text border border-info-border"
                        }`}
                      >
                        {change.field_label}
                      </span>
                      <span className="text-danger-text line-through">{change.old_value}</span>
                      <span className="text-text-tertiary">→</span>
                      <span className="text-success-text">{change.new_value}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Configuration Snapshot */}
            <div className="border-t border-border-default pt-4">
              <h4 className="font-medium text-text-secondary text-sm mb-2">Configuration Snapshot</h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                <div className="bg-surface-secondary p-2 rounded">
                  <span className="text-text-secondary text-xs">Model</span>
                  <p className="text-text-primary">{selectedItem.model}</p>
                </div>
                <div className="bg-surface-secondary p-2 rounded">
                  <span className="text-text-secondary text-xs">Temperature</span>
                  <p className="text-text-primary">{selectedItem.temperature}</p>
                </div>
                <div className="bg-surface-secondary p-2 rounded">
                  <span className="text-text-secondary text-xs">Langfuse</span>
                  <p className={selectedItem.langfuse_enabled ? "text-success-text" : "text-text-tertiary"}>
                    {selectedItem.langfuse_enabled ? "Enabled" : "Disabled"}
                  </p>
                </div>
                <div className="bg-surface-secondary p-2 rounded">
                  <span className="text-text-secondary text-xs">Auth Providers</span>
                  <p className="text-text-primary">
                    {[
                      selectedItem.auth_google_enabled && "Google",
                      selectedItem.auth_github_enabled && "GitHub",
                      selectedItem.auth_microsoft_enabled && "Microsoft",
                      selectedItem.auth_local_enabled && "Local",
                    ].filter(Boolean).join(", ") || "None"}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default ConfigurationHistoryPage;

import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { ConfigurableTable } from "../ui/Table";
import { Button } from "../ui/Button";
import { ConfirmModal, InputModal } from "../ui/Modal";
import { usePermissions } from "../../hooks/usePermissions";
import { PERMISSIONS } from "../../types/Permission";
import type { DatasetVersion } from "../../types/KnowledgeBase";
import {
  fetchDatasetVersions,
  rollbackToVersion,
  deleteVersion,
} from "../../handlers/knowledgeBaseHandlers";

const statusColors: Record<string, string> = {
  active: "bg-success-subtle text-success-text",
  inactive: "bg-surface-tertiary text-text-primary",
  ingesting: "bg-info-subtle text-info-text",
  archived: "bg-warning-subtle text-warning-text",
  failed: "bg-danger-subtle text-danger-text",
};

const VersionListPanel = ({ refreshTrigger = 0 }: { refreshTrigger?: number }) => {
  const { hasPermission } = usePermissions();
  const [versions, setVersions] = useState<DatasetVersion[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const pageSize = 10;

  // Modal state
  const [rollbackTarget, setRollbackTarget] = useState<DatasetVersion | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<DatasetVersion | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const loadVersions = async () => {
    setLoading(true);
    const result = await fetchDatasetVersions(pageSize, page * pageSize);
    if (result) {
      setVersions(result.versions);
      setTotal(result.total);
    }
    setLoading(false);
  };

  useEffect(() => {
    loadVersions();
  }, [page, refreshTrigger]);

  const handleRollback = async (reason: string) => {
    if (!rollbackTarget) return;
    setActionLoading(true);
    const result = await rollbackToVersion(rollbackTarget.id, reason);
    setActionLoading(false);
    setRollbackTarget(null);
    if (result.success) {
      toast.success(`Rolled back to version ${rollbackTarget.version_number}`);
      loadVersions();
    } else {
      toast.error(result.error || "Failed to rollback version");
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setActionLoading(true);
    const result = await deleteVersion(deleteTarget.id);
    setActionLoading(false);
    setDeleteTarget(null);
    if (result.success) {
      toast.success("Version deleted");
      loadVersions();
    } else {
      toast.error(result.error || "Failed to delete version");
    }
  };

  const columns = [
    {
      header: "Version",
      headerClassName: "font-medium text-text-secondary text-xs sticky top-0 bg-surface-secondary z-10 border-b border-border-default",
      className: "text-xs py-3",
      render: (item: DatasetVersion) => (
        <span className="font-medium">v{item.version_number}</span>
      ),
      searchable: false,
    },
    {
      header: "Source",
      headerClassName: "font-medium text-text-secondary text-xs sticky top-0 bg-surface-secondary z-10 border-b border-border-default",
      className: "text-xs py-3",
      render: (item: DatasetVersion) => {
        const label = item.source === "upload" ? "Upload"
          : item.source.charAt(0).toUpperCase() + item.source.slice(1);
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-info-subtle text-info-text">
            {label}
          </span>
        );
      },
      searchable: false,
    },
    {
      header: "Status",
      headerClassName: "font-medium text-text-secondary text-xs sticky top-0 bg-surface-secondary z-10 border-b border-border-default",
      className: "text-xs py-3",
      render: (item: DatasetVersion) => {
        let label = item.status.charAt(0).toUpperCase() + item.status.slice(1);
        if (item.is_active) label = "Active";
        if (item.status === "archived") label = "Archived (snapshot)";
        return (
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
              statusColors[item.status] || "bg-surface-tertiary text-text-primary"
            }`}
          >
            {label}
          </span>
        );
      },
      searchable: false,
    },
    {
      header: "Incidents",
      headerClassName: "font-medium text-text-secondary text-xs sticky top-0 bg-surface-secondary z-10 border-b border-border-default",
      className: "text-xs py-3",
      render: (item: DatasetVersion) => <span>{item.incident_count ?? "-"}</span>,
      searchable: false,
    },
    {
      header: "Uploaded By",
      headerClassName: "font-medium text-text-secondary text-xs sticky top-0 bg-surface-secondary z-10 border-b border-border-default",
      className: "text-xs py-3",
      render: (item: DatasetVersion) => <span>{item.uploader_email ?? "-"}</span>,
      searchable: false,
    },
    {
      header: "Created",
      headerClassName: "font-medium text-text-secondary text-xs sticky top-0 bg-surface-secondary z-10 border-b border-border-default",
      className: "text-xs py-3",
      render: (item: DatasetVersion) =>
        item.created_at ? new Date(item.created_at).toLocaleString() : "-",
      searchable: false,
    },
    {
      header: "Actions",
      headerClassName: "font-medium text-text-secondary text-xs sticky top-0 bg-surface-secondary z-10 border-b border-border-default",
      className: "text-xs py-3",
      render: (item: DatasetVersion) => (
        <div className="flex gap-1">
          {!item.is_active && item.status !== "archived" && item.status !== "failed" && (
            <>
              {hasPermission(PERMISSIONS.KB_ROLLBACK) && (
                <Button
                  variant="ghost"
                  size="sm"
                  rounded="lg"
                  onClick={() => setRollbackTarget(item)}
                >
                  Rollback
                </Button>
              )}
            </>
          )}
          {!item.is_active && hasPermission(PERMISSIONS.KB_VERSION_MANAGE) && (
            <Button
              variant="danger"
              size="sm"
              onClick={() => setDeleteTarget(item)}
            >
              Delete
            </Button>
          )}
        </div>
      ),
      searchable: false,
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-text-secondary">{total} version(s)</p>
        <Button variant="secondary" size="sm" onClick={loadVersions}>
          Refresh
        </Button>
      </div>

      {loading ? (
        <div className="text-sm text-text-secondary py-8 text-center">Loading versions...</div>
      ) : versions.length === 0 ? (
        <div className="text-sm text-text-secondary py-8 text-center">
          No dataset versions found. Upload and ingest incidents to create a version.
        </div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <ConfigurableTable data={versions} columns={columns} />
          </div>
          {total > pageSize && (
            <div className="flex items-center justify-between pt-2">
              <Button
                variant="secondary"
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="text-xs px-3 py-1"
              >
                Previous
              </Button>
              <span className="text-xs text-text-secondary">
                Page {page + 1} of {Math.ceil(total / pageSize)}
              </span>
              <Button
                variant="secondary"
                onClick={() => setPage((p) => p + 1)}
                disabled={(page + 1) * pageSize >= total}
                className="text-xs px-3 py-1"
              >
                Next
              </Button>
            </div>
          )}
        </>
      )}

      {/* Rollback modal */}
      <InputModal
        isOpen={!!rollbackTarget}
        onClose={() => setRollbackTarget(null)}
        onSubmit={handleRollback}
        title={`Rollback to Version ${rollbackTarget?.version_number}`}
        label="Reason for rollback"
        placeholder="e.g., New version contains incorrect data..."
        submitLabel="Rollback"
        isLoading={actionLoading}
        multiline
      />

      {/* Delete modal */}
      <ConfirmModal
        isOpen={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
        title="Delete Version"
        message={`Permanently delete version ${deleteTarget?.version_number}? This will also remove the Qdrant collection.`}
        confirmLabel="Delete"
        confirmVariant="danger"
        isLoading={actionLoading}
      />
    </div>
  );
};

export default VersionListPanel;

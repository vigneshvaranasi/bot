import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { Button } from "./ui/Button";
import Dropdown from "./ui/Dropdown";
import InputBox from "./ui/InputBox";
import { ConfirmModal } from "./ui/Modal";
import {
  AUTH_SCHEMAS,
  type IntegrationSyncStatus,
} from "../types/Integrations";
import type { IntegrationPayload } from "../handlers/integrationHandlers";

type IntegrationControlProps = {
  id?: string;
  serviceName: string;
  enabled?: boolean;
  syncStatus: IntegrationSyncStatus;
  lastSyncedAt?: string;
  lastError?: string;
  authType?: keyof typeof AUTH_SCHEMAS;
  config?: Record<string, string>;
  isNew?: boolean;
  readOnly?: boolean;
  onSave?: (
    payload: IntegrationPayload & { id?: string; isNew?: boolean }
  ) => Promise<void> | void;
  onDelete?: (id?: string, isNew?: boolean) => Promise<void> | void;
  onSync?: (
    id: string,
    callbacks: {
      onProgress: (msg: string, batch?: number, total?: number, incidents?: number) => void;
      onDone: () => void;
      onError: (msg: string) => void;
    }
  ) => Promise<void> | void;
};

const authOptions = [
  { value: "basic_auth", label: "Basic Auth" },
  { value: "api_token", label: "API Token" },
  { value: "oauth2", label: "OAuth 2.0" },
];

export default function IntegrationControl({
  id,
  serviceName,
  syncStatus,
  lastSyncedAt,
  lastError,
  enabled,
  authType: initialAuthType,
  config: initialConfig,
  isNew = false,
  readOnly = false,
  onSave,
  onDelete,
  onSync,
}: IntegrationControlProps) {
  const [authType, setAuthType] = useState<string | undefined>(initialAuthType);
  const [config, setConfig] = useState<Record<string, string>>(
    initialConfig || {}
  );
  const [error, setError] = useState<string | null>(null);
  const [isConfigOpen, setIsConfigOpen] = useState(isNew);
  const [isEnabled, setIsEnabled] = useState(enabled);
  const [name, setName] = useState(serviceName);
  const [isNameEditable, setIsNameEditable] = useState(isNew);
  const [isSaving, setIsSaving] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncProgress, setSyncProgress] = useState<string | null>(null);
  const [currentBatch, setCurrentBatch] = useState(0);
  const [totalBatches, setTotalBatches] = useState(0);
  const [totalIncidents, setTotalIncidents] = useState(0);

  // Delete confirmation modal state
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const nameInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    setAuthType(initialAuthType);
  }, [initialAuthType]);

  useEffect(() => {
    setConfig(initialConfig || {});
  }, [initialConfig]);

  useEffect(() => {
    setIsEnabled(enabled);
  }, [enabled]);

  useEffect(() => {
    setName(serviceName);
  }, [serviceName]);

  useEffect(() => {
    if (isNameEditable) {
      nameInputRef.current?.focus();
    }
  }, [isNameEditable]);

  const handleAuthChange = (value?: string) => {
    setAuthType(value);
    setConfig({});
    setError(null);
  };

  const validate = () => {
    if (!name.trim()) return "Service name is required";
    if (!authType) return "Authentication type is required";

    for (const field of AUTH_SCHEMAS[authType]) {
      if (field.required && !config[field.key]) {
        return `${field.label} is required`;
      }
    }
    return null;
  };

  const handleSave = async () => {
    if (!onSave || readOnly) return;

    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setError(null);
    setIsSaving(true);
    try {
      await onSave({
        id,
        service_name: name.trim(),
        auth_type: authType as string,
        config,
        is_active: Boolean(isEnabled),
        isNew,
      });
      setIsNameEditable(false);
    } catch (err) {
      console.error("Failed to save integration", err);
      setError("Failed to save integration");
    } finally {
      setIsSaving(false);
    }
  };

  const handleSync = async () => {
    if (!onSync || isNew || !id) return;
    setIsSyncing(true);
    setSyncProgress("Connecting to ServiceNow...");
    setCurrentBatch(0);
    setTotalBatches(0);
    setTotalIncidents(0);
    setError(null);
    try {
      await onSync(id, {
        onProgress: (msg: string, batch?: number, total?: number, incidents?: number) => {
          setSyncProgress(msg);
          if (batch !== undefined) setCurrentBatch(batch);
          if (total !== undefined) setTotalBatches(total);
          if (incidents !== undefined) setTotalIncidents(incidents);
        },
        onDone: () => {
          setSyncProgress(null);
          setCurrentBatch(0);
          setTotalBatches(0);
          setTotalIncidents(0);
          setIsSyncing(false);
          toast.success("Sync completed successfully");
        },
        onError: (msg: string) => {
          setSyncProgress(null);
          setCurrentBatch(0);
          setTotalBatches(0);
          setTotalIncidents(0);
          setIsSyncing(false);
          setError(msg);
          toast.error(msg);
        },
      });
    } catch (err) {
      console.error("Failed to sync integration", err);
      setError("Failed to sync integration");
      setSyncProgress(null);
      setCurrentBatch(0);
      setTotalBatches(0);
      setTotalIncidents(0);
      setIsSyncing(false);
    }
  };

  const openDeleteModal = () => {
    // For new integrations, just call onDelete without confirmation
    if (isNew) {
      onDelete?.(id, isNew);
      return;
    }
    setDeleteModalOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!onDelete || !id) return;

    setIsDeleting(true);
    try {
      await onDelete(id, isNew);
    } catch (err) {
      console.error("Failed to delete integration", err);
      setError("Failed to delete integration");
    } finally {
      setIsDeleting(false);
      setDeleteModalOpen(false);
    }
  };

  return (
    <div className="flex flex-col border border-gray-300 rounded-md p-4 gap-4">
      {/* Header */}
      <div className="flex flex-wrap justify-between items-center gap-2">
        <div className="flex items-center gap-2 min-w-0">
          {isNameEditable && !readOnly ? (
            <input
              ref={nameInputRef}
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-gray-400"
              placeholder="Enter service name"
            />
          ) : (
            <h3
              className={`text-lg font-semibold ${readOnly ? "" : "cursor-text"}`}
              onClick={() => {
                if (!readOnly) {
                  setIsNameEditable(true);
                  setIsConfigOpen(true);
                }
              }}
            >
              {name || "Unnamed Integration"}
            </h3>
          )}
          {readOnly && (
            <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">View only</span>
          )}
        </div>

        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1 text-sm">
            <input
              type="checkbox"
              checked={isEnabled}
              onChange={() => !readOnly && setIsEnabled((prev) => !prev)}
              disabled={readOnly}
            />
            Enabled
          </label>

          <Button
            variant="default"
            className="underline"
            onClick={() => setIsConfigOpen((prev) => !prev)}
          >
            {isConfigOpen ? "Close" : readOnly ? "View" : "Configure"}
          </Button>
        </div>
      </div>

      {/* Status */}
      <div className="text-sm text-gray-700 flex flex-wrap justify-between gap-2">
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <span>Status:</span>
            {syncStatus === "success" && (
              <span className="text-green-600 font-medium">✔ Success</span>
            )}
            {syncStatus === "error" && (
              <span className="text-red-600 font-medium">✖ Failed</span>
            )}
            {syncStatus === "never" && (
              <span className="text-gray-500">Never synced</span>
            )}
          </div>

          {lastSyncedAt && (
            <div className="text-xs text-gray-500">
              Last synced: {lastSyncedAt}
            </div>
          )}

          {lastError && (
            <div className="text-xs text-red-500">Last error: {lastError}</div>
          )}
        </div>

        {onSync && (
          <Button
            variant="secondary"
            className="w-fit font-normal"
            onClick={handleSync}
            disabled={isSyncing}
          >
            {isSyncing ? "Syncing..." : "Sync Now"}
          </Button>
        )}
      </div>

      {/* Sync Progress */}
      {syncProgress && (
        <div className="flex flex-col gap-2 px-4 py-3 bg-blue-50 border border-blue-200 rounded-md">
          <div className="flex items-center gap-2 text-sm text-blue-700">
            <svg className="animate-spin h-4 w-4 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span className="font-medium">{syncProgress}</span>
          </div>
          
          {totalBatches > 0 && (
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-blue-600">
                <span>Batch {currentBatch} of {totalBatches}</span>
                <span>{Math.round((currentBatch / totalBatches) * 100)}%</span>
              </div>
              <div className="w-full bg-blue-200 rounded-full h-2 overflow-hidden">
                <div 
                  className="bg-blue-600 h-2 rounded-full transition-all duration-300 ease-out"
                  style={{ width: `${Math.min((currentBatch / totalBatches) * 100, 100)}%` }}
                />
              </div>
              {totalIncidents > 0 && (
                <div className="text-xs text-blue-600 mt-1">
                  Processing {totalIncidents} incidents...
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Config */}
      {isConfigOpen && (
        <div className="flex flex-col gap-3 border-t border-gray-200 pt-4">
          <label className="text-sm font-medium">Authentication Type</label>
          <Dropdown
            options={authOptions}
            value={authType}
            onChange={readOnly ? () => {} : handleAuthChange}
            disabled={readOnly}
          />

          {authType && (
            <>
              <label className="text-sm font-medium mt-2">
                Integration Configuration
              </label>

              <div className="flex flex-col gap-3">
                {AUTH_SCHEMAS[authType].map((field) => (
                  <div key={field.key} className="flex flex-col gap-1">
                    <label className="text-xs font-medium">
                      {field.label}
                      {field.required && (
                        <span className="text-red-500"> *</span>
                      )}
                    </label>

                    <InputBox
                      value={String(config[field.key] || "")}
                      placeholder={field.label}
                      type={field.type === "url" ? "text" : field.type}
                      variant="primary"
                      onChange={readOnly ? () => {} : (value) =>
                        setConfig({
                          ...config,
                          [field.key]: value,
                        })
                      }
                      disabled={readOnly}
                    />
                  </div>
                ))}
              </div>
            </>
          )}

          {error && <span className="text-xs text-red-500">{error}</span>}
          {readOnly && (
            <p className="text-xs text-gray-500 mt-2">
              You don't have permission to edit this integration.
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            {onSave && !readOnly && (
              <Button
                variant="secondary"
                className="w-full sm:w-fit mt-2"
                onClick={handleSave}
                disabled={isSaving}
              >
                {isSaving ? "Saving..." : "Save Configuration"}
              </Button>
            )}
            {onDelete && !isSaving && (
              <Button
                variant="secondary"
                className={`w-full sm:w-fit mt-2 ${isNew ? "bg-gray-500 hover:bg-gray-700" : "bg-red-500 hover:bg-red-800 border-red-300"}`}
                onClick={openDeleteModal}
                disabled={isDeleting}
              >
                {isNew ? "Cancel" : isDeleting ? "Deleting..." : "Delete"}
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      <ConfirmModal
        isOpen={deleteModalOpen}
        onClose={() => setDeleteModalOpen(false)}
        onConfirm={handleConfirmDelete}
        title="Delete Integration"
        message={`Are you sure you want to delete "${name}"? This action cannot be undone.`}
        confirmLabel="Delete"
        cancelLabel="Cancel"
        confirmVariant="danger"
        isLoading={isDeleting}
      />
    </div>
  );
}

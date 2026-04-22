import { useEffect, useMemo, useRef, useState } from "react";
import toast from "react-hot-toast";
import { Button } from "./ui/Button";
import Dropdown from "./ui/Dropdown";
import InputBox from "./ui/InputBox";
import { ConfirmModal } from "./ui/Modal";
import {
  AUTH_TYPE_LABELS,
  getAuthFields,
  getAuthTypesForConnector,
  type AuthType,
  type ConnectorType,
  type IntegrationSyncStatus,
} from "../types/Integrations";
import type { IntegrationPayload } from "../handlers/integrationHandlers";

const normalizeConfig = (value?: Record<string, string>) =>
  JSON.stringify(value || {});

const isSensitiveField = (key: string) => {
  const lowered = key.toLowerCase();
  return (
    lowered.includes("password") ||
    lowered.includes("secret") ||
    lowered.includes("token") ||
    lowered === "api_key"
  );
};

type IntegrationControlProps = {
  id?: string;
  serviceName: string;
  connectorType: ConnectorType;
  enabled?: boolean;
  syncStatus: IntegrationSyncStatus;
  lastSyncedAt?: string;
  lastError?: string;
  authType?: AuthType;
  config?: Record<string, string>;
  configuredSecrets?: string[];
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

export default function IntegrationControl({
  id,
  serviceName,
  connectorType,
  syncStatus,
  lastSyncedAt,
  lastError,
  enabled,
  authType: initialAuthType,
  config: initialConfig,
  configuredSecrets: initialConfiguredSecrets = [],
  isNew = false,
  readOnly = false,
  onSave,
  onDelete,
  onSync,
}: IntegrationControlProps) {
  const [authType, setAuthType] = useState<AuthType | undefined>(initialAuthType);
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

  const authOptions = useMemo(
    () =>
      getAuthTypesForConnector(connectorType).map((value) => ({
        value,
        label: AUTH_TYPE_LABELS[value],
      })),
    [connectorType]
  );

  const fields = useMemo(
    () => (authType ? getAuthFields(connectorType, authType) : []),
    [connectorType, authType]
  );

  const isDirty =
    name.trim() !== serviceName ||
    authType !== initialAuthType ||
    Boolean(isEnabled) !== Boolean(enabled) ||
    normalizeConfig(config) !== normalizeConfig(initialConfig);

  const handleAuthChange = (value?: string) => {
    setAuthType(value as AuthType | undefined);
    setConfig({});
    setError(null);
  };

  const validate = () => {
    if (!name.trim()) return "Service name is required";
    if (!authType) return "Authentication type is required";

    for (const field of fields) {
      const hasConfiguredSecret =
        !isNew &&
        authType === initialAuthType &&
        isSensitiveField(field.key) &&
        initialConfiguredSecrets.includes(field.key) &&
        !config[field.key];
      if (field.required && !config[field.key] && !hasConfiguredSecret) {
        return `${field.label} is required`;
      }
    }

    if (connectorType === "jira") {
      const hasProject = (config.project_key || "").trim().length > 0;
      const hasJql = (config.jql || "").trim().length > 0;
      if (!hasProject && !hasJql) {
        return "Provide either a Project Key or a custom JQL query";
      }
    }
    return null;
  };

  const handleSave = async () => {
    if (!onSave || readOnly) return;
    if (!isDirty) return;

    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setError(null);
    setIsSaving(true);
    try {
      const payloadConfig: Record<string, string> = {};
      for (const [key, value] of Object.entries(config)) {
        const sensitive = isSensitiveField(key);

        if (sensitive && !value && initialConfiguredSecrets.includes(key)) {
          continue;
        }

        payloadConfig[key] = value;
      }

      await onSave({
        id,
        service_name: name.trim(),
        connector_type: connectorType,
        auth_type: authType as AuthType,
        config: payloadConfig,
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
    setSyncProgress(`Connecting to ${name || "integration"}...`);
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
    <div className="flex flex-col border border-border-strong rounded-md p-4 gap-4">
      {/* Header */}
      <div className="flex flex-wrap justify-between items-center gap-2">
        <div className="flex items-center gap-2 min-w-0">
          {isNameEditable && !readOnly ? (
            <input
              ref={nameInputRef}
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="border border-border-strong rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-gray-400"
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
          <span className="text-xs text-text-secondary bg-surface-tertiary px-2 py-0.5 rounded">
            {connectorType}
          </span>
          {readOnly && (
            <span className="text-xs text-text-secondary bg-surface-tertiary px-2 py-0.5 rounded">View only</span>
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
      <div className="text-sm text-text-secondary flex flex-wrap justify-between gap-2">
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <span>Status:</span>
            {syncStatus === "success" && (
              <span className="text-success-text font-medium">✔ Success</span>
            )}
            {syncStatus === "error" && (
              <span className="text-danger-text font-medium">✖ Failed</span>
            )}
            {syncStatus === "never" && (
              <span className="text-text-secondary">Never synced</span>
            )}
          </div>

          {lastSyncedAt && (
            <div className="text-xs text-text-secondary">
              Last synced: {lastSyncedAt}
            </div>
          )}

          {lastError && (
            <div className="text-xs text-danger-text">Last error: {lastError}</div>
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
        <div className="flex flex-col gap-2 px-4 py-3 bg-info-subtle border border-info-border rounded-md">
          <div className="flex items-center gap-2 text-sm text-info-text">
            <svg className="animate-spin h-4 w-4 text-accent-blue" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span className="font-medium">{syncProgress}</span>
          </div>

          {totalBatches > 0 && (
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-accent-blue">
                <span>Batch {currentBatch} of {totalBatches}</span>
                <span>{Math.round((currentBatch / totalBatches) * 100)}%</span>
              </div>
              <div className="w-full bg-surface-hover rounded-full h-2 overflow-hidden">
                <div
                  className="bg-accent-blue h-2 rounded-full transition-all duration-300 ease-out"
                  style={{ width: `${Math.min((currentBatch / totalBatches) * 100, 100)}%` }}
                />
              </div>
              {totalIncidents > 0 && (
                <div className="text-xs text-accent-blue mt-1">
                  Processing {totalIncidents} incidents...
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Config */}
      {isConfigOpen && (
        <div className="flex flex-col gap-3 border-t border-border-default pt-4">
          <label className="text-sm font-medium">Authentication Type</label>
          <Dropdown
            className="block w-full"
            options={authOptions}
            value={authType}
            onChange={readOnly ? () => {} : handleAuthChange}
            disabled={readOnly}
          />

          {authType && fields.length > 0 && (
            <>
              <label className="text-sm font-medium mt-2">
                Integration Configuration
              </label>

              <div className="flex flex-col gap-3">
                {fields.map((field) => (
                  <div key={field.key} className="flex flex-col gap-1">
                    <label className="text-xs font-medium">
                      {field.label}
                      {field.required && (
                        <span className="text-danger-text"> *</span>
                      )}
                    </label>

                    <InputBox
                      value={String(config[field.key] || "")}
                      placeholder={
                        isSensitiveField(field.key) && initialConfiguredSecrets.includes(field.key)
                          ? "••••••••"
                          : field.placeholder || field.label
                      }
                      type={
                        field.type === "password"
                          ? "password"
                          : "text"
                      }
                      variant={field.type === "textarea" ? "multiline" : "primary"}
                      onChange={readOnly ? () => {} : (value) =>
                        setConfig((prev) => ({
                          ...prev,
                          [field.key]: value,
                        }))
                      }
                      disabled={readOnly}
                    />
                    {field.help && (
                      <span className="text-[11px] text-text-secondary">{field.help}</span>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}

          {error && <span className="text-xs text-danger-text">{error}</span>}
          {readOnly && (
            <p className="text-xs text-text-secondary mt-2">
              You don't have permission to edit this integration.
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            {onSave && !readOnly && (
              <Button
                variant="primary"
                className="w-full sm:w-fit mt-2"
                onClick={handleSave}
                disabled={isSaving || !isDirty}
              >
                {isSaving ? "Saving..." : "Save Configuration"}
              </Button>
            )}
            {onDelete && !isSaving && (
              <Button
                variant={isNew ? "ghost" : "danger"}
                className="w-full sm:w-fit mt-2"
                onClick={openDeleteModal}
                disabled={isDeleting}
              >
                {isNew ? "Cancel" : isDeleting ? "Deleting..." : "Delete"}
              </Button>
            )}
          </div>
        </div>
      )}

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
      {!readOnly && isConfigOpen && !isDirty && (
        <p className="text-xs text-text-secondary">
          No changes to save.
        </p>
      )}
    </div>
  );
}

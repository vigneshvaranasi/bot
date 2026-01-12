import { useEffect, useRef, useState } from "react";
import { Button } from "./ui/Button";
import Dropdown from "./ui/Dropdown";
import InputBox from "./ui/InputBox";
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
  onSave: (
    payload: IntegrationPayload & { id?: string; isNew?: boolean }
  ) => Promise<void> | void;
  onDelete?: (id?: string, isNew?: boolean) => Promise<void> | void;
  onSync?: (id?: string) => Promise<void> | void;
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
    try {
      await onSync(id);
    } catch (err) {
      console.error("Failed to sync integration", err);
      setError("Failed to sync integration");
    } finally {
      setIsSyncing(false);
    }
  };

  return (
    <div className="flex flex-col border border-gray-300 rounded-md p-4 gap-4">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-2">
          {isNameEditable ? (
            <input
              ref={nameInputRef}
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-gray-400"
              placeholder="Enter service name"
            />
          ) : (
            <h3
              className="text-lg font-semibold cursor-text"
              onClick={() => {
                setIsNameEditable(true);
                setIsConfigOpen(true);
              }}
            >
              {name || "Unnamed Integration"}
            </h3>
          )}
        </div>

        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1 text-sm">
            <input
              type="checkbox"
              checked={isEnabled}
              onChange={() => setIsEnabled((prev) => !prev)}
            />
            Enabled
          </label>

          <Button
            variant="default"
            className="underline"
            onClick={() => setIsConfigOpen((prev) => !prev)}
          >
            {isConfigOpen ? "Close" : "Configure"}
          </Button>
        </div>
      </div>

      {/* Status */}
      <div className="text-sm text-gray-700 flex flex-row justify-between gap-1">
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

        <Button
          variant="secondary"
          className="w-fit font-normal"
          onClick={handleSync}
          disabled={isSyncing}
        >
          {isSyncing ? "Syncing..." : "Sync Now"}
        </Button>
      </div>

      {/* Config */}
      {isConfigOpen && (
        <div className="flex flex-col gap-3 border-t border-gray-200 pt-4">
          <label className="text-sm font-medium">Authentication Type</label>
          <Dropdown
            options={authOptions}
            value={authType}
            onChange={handleAuthChange}
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
                      onChange={(value) =>
                        setConfig({
                          ...config,
                          [field.key]: value,
                        })
                      }
                    />
                  </div>
                ))}
              </div>
            </>
          )}

          {error && <span className="text-xs text-red-500">{error}</span>}
          <div className="flex flex-row gap-2">
            <Button
              variant="secondary"
              className="w-fit mt-2"
              onClick={handleSave}
              disabled={isSaving}
            >
              {isSaving ? "Saving..." : "Save Configuration"}
            </Button>
            {onDelete && !isSaving && (
              <Button
                variant="secondary"
                className="w-fit mt-2 bg-red-500 hover:bg-red-800 border-red-300"
                onClick={() => onDelete(id, isNew)}
              >
                Delete
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

import { useEffect, useRef, useState } from "react";
import { Button } from "./ui/Button";
import Dropdown from "./ui/Dropdown";
import InputBox from "./ui/InputBox";
import { ConfirmModal } from "./ui/Modal";
import type {
  LlmProvider,
  LlmProviderCreate,
  LlmProviderUpdate,
  ProviderType,
  HealthCheckResult,
} from "../types/LlmProvider";
import {
  PROVIDER_FIELDS,
  PROVIDER_LABELS,
  PROVIDER_COLORS,
  AUTH_TYPE_OPTIONS,
} from "../types/LlmProvider";

type ModelDiscoveryResult = {
  success: boolean;
  models: string[];
  message: string;
};

type LlmProviderControlProps = {
  provider?: LlmProvider;
  isNew?: boolean;
  onSave?: (payload: LlmProviderCreate | (LlmProviderUpdate & { id: string })) => Promise<void>;
  onDelete?: (id?: string) => void | Promise<void>;
  onTest?: (id: string) => Promise<HealthCheckResult | null>;
  onDiscoverModels?: (id: string) => Promise<ModelDiscoveryResult | null>;
  onDiscoverModelsFromConfig?: (config: LlmProviderCreate) => Promise<ModelDiscoveryResult | null>;
  // Permission flags
  canEdit?: boolean;
  canDelete?: boolean;
  canTest?: boolean;
};

const providerTypeOptions = [
  { value: "anthropic", label: PROVIDER_LABELS.anthropic },
  { value: "openai", label: PROVIDER_LABELS.openai },
  { value: "google", label: PROVIDER_LABELS.google },
  { value: "custom", label: PROVIDER_LABELS.custom },
];

export default function LlmProviderControl({
  provider,
  isNew = false,
  onSave,
  onDelete,
  onTest,
  onDiscoverModels,
  onDiscoverModelsFromConfig,
  canEdit = true,
  canDelete = true,
  canTest = true,
}: LlmProviderControlProps) {
  // Form state
  const [name, setName] = useState(provider?.name || "");
  const [providerType, setProviderType] = useState<ProviderType | "">(
    provider?.provider_type || ""
  );
  const [baseUrl, setBaseUrl] = useState(provider?.base_url || "");
  const [apiKey, setApiKey] = useState("");
  const [selectedModels, setSelectedModels] = useState<string[]>(provider?.models || []);
  const [newModel, setNewModel] = useState("");
  const [isActive, setIsActive] = useState(provider?.is_active ?? true);
  const [isDefault, setIsDefault] = useState(provider?.is_default ?? false);

  // Custom provider config
  const [authType, setAuthType] = useState<string>(
    provider?.config?.auth_type || "none"
  );
  const [authHeaderName, setAuthHeaderName] = useState(
    provider?.config?.auth_header_name || "X-API-Key"
  );
  const [organizationId, setOrganizationId] = useState(
    provider?.config?.organization_id || ""
  );

  // Model discovery state
  const [discoveredModels, setDiscoveredModels] = useState<string[]>([]);
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [discoveryError, setDiscoveryError] = useState<string | null>(null);

  // UI state
  const [isConfigOpen, setIsConfigOpen] = useState(isNew);
  const [isNameEditable, setIsNameEditable] = useState(isNew);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<HealthCheckResult | null>(null);

  // Delete confirmation modal state
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const nameInputRef = useRef<HTMLInputElement | null>(null);

  // Reset form when provider changes
  useEffect(() => {
    if (provider) {
      setName(provider.name);
      setProviderType(provider.provider_type);
      setBaseUrl(provider.base_url || "");
      setSelectedModels(provider.models || []);
      setIsActive(provider.is_active);
      setIsDefault(provider.is_default);
      setAuthType(provider.config?.auth_type || "none");
      setAuthHeaderName(provider.config?.auth_header_name || "X-API-Key");
      setOrganizationId(provider.config?.organization_id || "");
    }
  }, [provider]);

  // Focus name input when editable
  useEffect(() => {
    if (isNameEditable) {
      nameInputRef.current?.focus();
    }
  }, [isNameEditable]);

  const fieldConfig = providerType ? PROVIDER_FIELDS[providerType] : null;

  const validate = (): string | null => {
    if (!name.trim()) return "Provider name is required";
    if (!providerType) return "Provider type is required";

    if (fieldConfig) {
      if (fieldConfig.apiKeyRequired && !apiKey && !provider?.has_api_key) {
        return "API key is required";
      }
      if (fieldConfig.baseUrlRequired && !baseUrl) {
        return "Base URL is required";
      }
    }

    // Models are recommended but not required - allow saving without them
    return null;
  };

  // Check if we have enough info to discover models
  const canDiscoverModels = (): boolean => {
    if (!providerType) return false;
    if (!fieldConfig) return false;

    // For custom providers, need base URL
    if (providerType === "custom") {
      return !!baseUrl;
    }

    // For other providers, need API key (either new or existing)
    return !!(apiKey || provider?.has_api_key);
  };

  const handleProviderTypeChange = (value?: string) => {
    const newType = value as ProviderType;
    setProviderType(newType);
    setApiKey("");
    setBaseUrl("");
    setError(null);
    setTestResult(null);
    setDiscoveredModels([]);
    setSelectedModels([]);
    setDiscoveryError(null);
  };

  const handleAddModel = () => {
    const trimmed = newModel.trim();
    if (trimmed && !selectedModels.includes(trimmed)) {
      setSelectedModels([...selectedModels, trimmed]);
      setNewModel("");
    }
  };

  const handleRemoveModel = (modelToRemove: string) => {
    setSelectedModels(selectedModels.filter((m) => m !== modelToRemove));
  };

  const handleToggleDiscoveredModel = (model: string) => {
    if (selectedModels.includes(model)) {
      setSelectedModels(selectedModels.filter((m) => m !== model));
    } else {
      setSelectedModels([...selectedModels, model]);
    }
  };

  const handleSelectAllDiscovered = () => {
    const newModels = discoveredModels.filter((m) => !selectedModels.includes(m));
    setSelectedModels([...selectedModels, ...newModels]);
  };

  const handleSave = async () => {
    if (!onSave) return;

    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setError(null);
    setIsSaving(true);

    try {
      const config: Record<string, unknown> = {};

      if (providerType === "custom") {
        config.auth_type = authType;
        if (authType === "api_key_header") {
          config.auth_header_name = authHeaderName;
        }
      }

      if (providerType === "openai" && organizationId) {
        config.organization_id = organizationId;
      }

      if (isNew) {
        const payload: LlmProviderCreate = {
          name: name.trim(),
          provider_type: providerType as ProviderType,
          base_url: baseUrl || null,
          api_key: apiKey || null,
          config,
          models: selectedModels,
          is_active: isActive,
          is_default: isDefault,
        };
        await onSave(payload);
      } else if (provider) {
        const payload: LlmProviderUpdate & { id: string } = {
          id: provider.id,
          name: name.trim(),
          base_url: baseUrl || null,
          config,
          models: selectedModels,
          is_active: isActive,
          is_default: isDefault,
        };

        // Only include API key if it was changed
        if (apiKey) {
          payload.api_key = apiKey;
        }

        await onSave(payload);
      }

      setIsNameEditable(false);
      setApiKey(""); // Clear API key after save
    } catch (err) {
      console.error("Failed to save provider", err);
      setError("Failed to save provider");
    } finally {
      setIsSaving(false);
    }
  };

  const handleTest = async () => {
    if (!onTest || !provider?.id) return;

    setIsTesting(true);
    setTestResult(null);
    setDiscoveryError(null);

    try {
      const result = await onTest(provider.id);
      setTestResult(result);

      // Auto-discover models if test was successful
      if (result?.success && onDiscoverModels) {
        await handleDiscoverModels();
      }
    } catch (err) {
      console.error("Failed to test connection", err);
      setError("Failed to test connection");
    } finally {
      setIsTesting(false);
    }
  };

  const handleDiscoverModels = async () => {
    // For saved providers, use the ID-based discovery
    if (provider?.id && onDiscoverModels) {
      setIsDiscovering(true);
      setDiscoveryError(null);

      try {
        const result = await onDiscoverModels(provider.id);
        if (result?.success && result.models.length > 0) {
          setDiscoveredModels(result.models);
          // Auto-select discovered models if none are currently selected
          if (selectedModels.length === 0) {
            setSelectedModels(result.models.slice(0, 5)); // Select first 5 by default
          }
        } else {
          setDiscoveryError(result?.message || "No models found");
        }
      } catch (err) {
        console.error("Failed to discover models", err);
        setDiscoveryError("Failed to discover models");
      } finally {
        setIsDiscovering(false);
      }
      return;
    }

    // For new/unsaved providers, use config-based discovery
    if (!onDiscoverModelsFromConfig || !providerType) return;

    setIsDiscovering(true);
    setDiscoveryError(null);

    try {
      const config: Record<string, unknown> = {};

      if (providerType === "custom") {
        config.auth_type = authType;
        if (authType === "api_key_header") {
          config.auth_header_name = authHeaderName;
        }
      }

      if (providerType === "openai" && organizationId) {
        config.organization_id = organizationId;
      }

      const payload: LlmProviderCreate = {
        name: name.trim() || "Temp",
        provider_type: providerType as ProviderType,
        base_url: baseUrl || null,
        api_key: apiKey || null,
        config,
        models: [],
        is_active: true,
        is_default: false,
      };

      const result = await onDiscoverModelsFromConfig(payload);
      if (result?.success && result.models.length > 0) {
        setDiscoveredModels(result.models);
        // Auto-select discovered models if none are currently selected
        if (selectedModels.length === 0) {
          setSelectedModels(result.models.slice(0, 5)); // Select first 5 by default
        }
      } else {
        setDiscoveryError(result?.message || "No models found");
      }
    } catch (err) {
      console.error("Failed to discover models from config", err);
      setDiscoveryError("Failed to discover models");
    } finally {
      setIsDiscovering(false);
    }
  };

  const openDeleteModal = () => {
    // For new providers, just call onDelete without confirmation
    if (isNew) {
      onDelete?.();
      return;
    }
    setDeleteModalOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!onDelete || !provider?.id) return;

    setIsDeleting(true);
    try {
      await onDelete(provider.id);
    } catch (err) {
      console.error("Failed to delete provider", err);
      setError("Failed to delete provider");
    } finally {
      setIsDeleting(false);
      setDeleteModalOpen(false);
    }
  };

  const formatLastCheck = () => {
    if (!provider?.last_health_check_at) return null;
    const date = new Date(provider.last_health_check_at);
    return date.toLocaleString();
  };

  return (
    <div className="flex flex-col border border-gray-200 rounded-lg px-3 py-2.5 gap-2">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-2">
          {isNameEditable && canEdit ? (
            <input
              ref={nameInputRef}
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="border border-gray-300 rounded px-2 py-0.5 text-sm focus:outline-none focus:ring-1 focus:ring-gray-400"
              placeholder="Enter provider name"
            />
          ) : (
            <h3
              className={`text-sm font-semibold text-gray-900 ${canEdit ? "cursor-text" : ""}`}
              onClick={() => {
                if (canEdit) {
                  setIsNameEditable(true);
                  setIsConfigOpen(true);
                }
              }}
            >
              {name || "Unnamed Provider"}
            </h3>
          )}

          {providerType && (
            <span
              className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${PROVIDER_COLORS[providerType]}`}
            >
              {PROVIDER_LABELS[providerType]}
            </span>
          )}

          {isDefault && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-yellow-100 text-yellow-800 font-medium">
              Default
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <label className="flex items-center gap-1 text-xs text-gray-600">
            <input
              type="checkbox"
              checked={isActive}
              onChange={() => setIsActive((prev) => !prev)}
              className="w-3.5 h-3.5"
            />
            Active
          </label>

          <button
            className="text-xs text-accent hover:underline cursor-pointer"
            onClick={() => setIsConfigOpen((prev) => !prev)}
          >
            {isConfigOpen ? "Close" : "Configure"}
          </button>
        </div>
      </div>

      {/* Status */}
      <div className="flex items-center justify-between gap-2 text-xs text-gray-600">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1">
            <span>Health:</span>
            {provider?.last_health_check_status === "success" && (
              <span className="text-green-600 font-medium">✔ Healthy</span>
            )}
            {provider?.last_health_check_status === "error" && (
              <span className="text-red-600 font-medium">✖ Unhealthy</span>
            )}
            {!provider?.last_health_check_status && (
              <span className="text-gray-400">Not tested</span>
            )}
          </div>

          {provider?.last_health_check_at && (
            <span className="text-gray-400">
              {formatLastCheck()}
            </span>
          )}

          {provider?.last_health_check_error && (
            <span className="text-red-500">
              {provider.last_health_check_error}
            </span>
          )}

          {testResult && (
            <span className={testResult.success ? "text-green-600" : "text-red-500"}>
              {testResult.success
                ? `✔ OK (${testResult.response_time_ms?.toFixed(0)}ms)`
                : `✖ ${testResult.message}`}
            </span>
          )}
        </div>

        {!isNew && provider?.id && canTest && onTest && (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleTest}
            disabled={isTesting || isDiscovering}
          >
            {isTesting ? "Testing..." : isDiscovering ? "Discovering..." : "Test & Discover"}
          </Button>
        )}
      </div>

      {/* Config */}
      {isConfigOpen && (
        <div className="flex flex-col gap-2.5 border-t border-gray-100 pt-3">
          {/* Form fields in 2-col grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2.5">
            {/* Provider Type */}
            <div className="flex flex-col gap-0.5">
              <label className="text-xs font-medium text-gray-700">Provider Type</label>
              <Dropdown
                options={providerTypeOptions}
                value={providerType}
                onChange={handleProviderTypeChange}
                disabled={!isNew && !!provider}
              />
            </div>

            {fieldConfig && (
              <>
                {fieldConfig.showBaseUrl && (
                  <div className="flex flex-col gap-0.5 sm:col-span-2">
                    <label className="text-xs font-medium text-gray-700">
                      Base URL
                      {fieldConfig.baseUrlRequired && <span className="text-red-500"> *</span>}
                    </label>
                    <InputBox
                      value={baseUrl}
                      placeholder={fieldConfig.baseUrlPlaceholder}
                      type="text"
                      variant="primary"
                      onChange={setBaseUrl}
                    />
                  </div>
                )}

                {fieldConfig.showApiKey && (
                  <div className="flex flex-col gap-0.5">
                    <label className="text-xs font-medium text-gray-700">
                      API Key
                      {fieldConfig.apiKeyRequired && !provider?.has_api_key && (
                        <span className="text-red-500"> *</span>
                      )}
                      {provider?.has_api_key && (
                        <span className="text-gray-400 ml-1">(keep existing)</span>
                      )}
                    </label>
                    <InputBox
                      value={apiKey}
                      placeholder={
                        provider?.has_api_key
                          ? "••••••••••••••••"
                          : fieldConfig.apiKeyPlaceholder
                      }
                      type="password"
                      variant="primary"
                      onChange={setApiKey}
                    />
                  </div>
                )}

                {fieldConfig.showOrganizationId && (
                  <div className="flex flex-col gap-0.5">
                    <label className="text-xs font-medium text-gray-700">
                      Organization ID <span className="text-gray-400">(optional)</span>
                    </label>
                    <InputBox
                      value={organizationId}
                      placeholder="org-..."
                      type="text"
                      variant="primary"
                      onChange={setOrganizationId}
                    />
                  </div>
                )}

                {fieldConfig.showAuthType && (
                  <div className="flex flex-col gap-0.5">
                    <label className="text-xs font-medium text-gray-700">Auth Type</label>
                    <Dropdown
                      options={AUTH_TYPE_OPTIONS}
                      value={authType}
                      onChange={(v) => setAuthType(v || "none")}
                    />
                  </div>
                )}

                {fieldConfig.showAuthType && authType === "api_key_header" && (
                  <div className="flex flex-col gap-0.5">
                    <label className="text-xs font-medium text-gray-700">Header Name</label>
                    <InputBox
                      value={authHeaderName}
                      placeholder="X-API-Key"
                      type="text"
                      variant="primary"
                      onChange={setAuthHeaderName}
                    />
                  </div>
                )}
              </>
            )}
          </div>

          {/* Discover Models */}
          {fieldConfig && canDiscoverModels() && (
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleDiscoverModels}
                disabled={isDiscovering}
              >
                {isDiscovering ? "Discovering..." : "Discover Models"}
              </Button>
              <span className="text-xs text-gray-400">Fetch available models from the provider API</span>
            </div>
          )}

          {/* Discovered Models */}
          {discoveredModels.length > 0 && (
            <div className="flex flex-col gap-1.5 p-2 bg-blue-50 rounded-md">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-blue-800">
                  Discovered ({discoveredModels.length})
                </span>
                <button
                  type="button"
                  onClick={handleSelectAllDiscovered}
                  className="text-[10px] text-blue-600 hover:text-blue-800 underline"
                >
                  Select All
                </button>
              </div>
              <div className="flex flex-wrap gap-1">
                {discoveredModels.map((model) => {
                  const isSelected = selectedModels.includes(model);
                  return (
                    <button
                      key={model}
                      type="button"
                      onClick={() => handleToggleDiscoveredModel(model)}
                      className={`px-1.5 py-0.5 rounded text-[11px] transition-colors ${
                        isSelected
                          ? "bg-blue-600 text-white"
                          : "bg-white text-gray-700 border border-gray-300 hover:bg-gray-100"
                      }`}
                    >
                      {model}
                      {isSelected && " ✓"}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {discoveryError && (
            <div className="text-xs text-amber-600 bg-amber-50 px-2 py-1 rounded">
              {discoveryError}. You can manually add models below.
            </div>
          )}

          {/* Selected Models */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-gray-700">
              Selected Models
              <span className="text-gray-400 ml-1">({selectedModels.length})</span>
            </label>

            {selectedModels.length > 0 ? (
              <div className="flex flex-wrap gap-1">
                {selectedModels.map((model) => (
                  <span
                    key={model}
                    className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-green-50 text-green-700 border border-green-200 rounded text-[11px]"
                  >
                    {model}
                    <button
                      type="button"
                      onClick={() => handleRemoveModel(model)}
                      className="text-green-500 hover:text-red-500"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-400">
                {canDiscoverModels()
                  ? "Click 'Discover Models' to find available models."
                  : "Enter credentials to discover available models."}
              </p>
            )}

            <div className="flex gap-2 items-center">
              <InputBox
                value={newModel}
                placeholder="Add model ID manually"
                type="text"
                variant="primary"
                onChange={setNewModel}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleAddModel();
                  }
                }}
              />
              <Button variant="ghost" size="sm" onClick={handleAddModel}>
                Add
              </Button>
            </div>
          </div>

          {/* Default toggle */}
          <label className="flex items-center gap-1.5 text-xs text-gray-700">
            <input
              type="checkbox"
              checked={isDefault}
              onChange={() => setIsDefault((prev) => !prev)}
              className="w-3.5 h-3.5"
            />
            Set as default provider
          </label>

          {error && <span className="text-xs text-red-500">{error}</span>}

          {/* Action buttons */}
          <div className="flex items-center gap-2 pt-1 border-t border-gray-100">
            {canEdit && onSave && (
              <Button
                variant="secondary"
                size="sm"
                onClick={handleSave}
                disabled={isSaving}
              >
                {isSaving ? "Saving..." : "Save"}
              </Button>
            )}

            {((isNew && canEdit) || (!isNew && canDelete)) && onDelete && (isNew || provider?.id) && (
              <Button
                variant={isNew ? "ghost" : "danger"}
                size="sm"
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
        title="Delete Provider"
        message={`Are you sure you want to delete "${name}"? This action cannot be undone.`}
        confirmLabel="Delete"
        cancelLabel="Cancel"
        confirmVariant="danger"
        isLoading={isDeleting}
      />
    </div>
  );
}

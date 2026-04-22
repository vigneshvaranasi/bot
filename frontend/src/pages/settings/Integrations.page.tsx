import { useEffect, useMemo, useState } from "react";
import SettingsHeader from "../../components/settings/SettingsHeader";
import { Button } from "../../components/ui/Button";
import IntegrationControl from "../../components/IntegrationControl";
import InfoHint from "../../components/ui/InfoHint";
import Modal from "../../components/ui/Modal";
import Dropdown from "../../components/ui/Dropdown";
import InputBox from "../../components/ui/InputBox";
import {
  fetchIntegrations,
  createIntegration,
  updateIntegration,
  deleteIntegration,
  syncIntegration,
  type IntegrationPayload,
} from "../../handlers/integrationHandlers";
import {
  AUTH_TYPE_LABELS,
  CONNECTOR_TYPES,
  getAuthFields,
  getAuthTypesForConnector,
  type AuthType,
  type ConnectorType,
  type Integration,
  type IntegrationSyncStatus,
} from "../../types/Integrations";
import { SkeletonIntegrations } from "../../components/ui/Skeleton";
import { usePermissions } from "../../hooks/usePermissions";
import { PERMISSIONS } from "../../types/Permission";

const IntegrationsPage = () => {
  const { hasPermission } = usePermissions();
  const canCreate = hasPermission(PERMISSIONS.INTEGRATION_CREATE);
  const canEdit = hasPermission(PERMISSIONS.INTEGRATION_EDIT);
  const canDelete = hasPermission(PERMISSIONS.INTEGRATION_DELETE);
  const canSync = hasPermission(PERMISSIONS.INTEGRATION_SYNC);
  type IntegrationItem = Integration & { isNew?: boolean };

  const [integrations, setIntegrations] = useState<IntegrationItem[]>([]);
  const [integrationsLoading, setIntegrationsLoading] = useState(false);
  const [integrationsError, setIntegrationsError] = useState<string | null>(null);

  const [addModalOpen, setAddModalOpen] = useState(false);
  const [newConnectorType, setNewConnectorType] = useState<ConnectorType | undefined>(undefined);
  const [newName, setNewName] = useState("");
  const [newAuthType, setNewAuthType] = useState<AuthType | undefined>(undefined);
  const [newConfig, setNewConfig] = useState<Record<string, string>>({});
  const [addError, setAddError] = useState<string | null>(null);
  const [isAdding, setIsAdding] = useState(false);

  const connectorOptions = CONNECTOR_TYPES.map((c) => ({ value: c.value, label: c.label }));

  const newAuthOptions = useMemo(() => {
    if (!newConnectorType) return [];
    return getAuthTypesForConnector(newConnectorType).map((value) => ({
      value,
      label: AUTH_TYPE_LABELS[value],
    }));
  }, [newConnectorType]);

  const newFields = useMemo(() => {
    if (!newConnectorType || !newAuthType) return [];
    return getAuthFields(newConnectorType, newAuthType);
  }, [newConnectorType, newAuthType]);

  useEffect(() => {
    const loadIntegrations = async () => {
      setIntegrationsLoading(true);
      setIntegrationsError(null);
      try {
        const result = await fetchIntegrations();
        if (result) {
          setIntegrations(result);
        } else {
          setIntegrationsError("Unable to load integrations");
        }
      } catch (error) {
        console.error("Error fetching integrations:", error);
        setIntegrationsError("Failed to fetch integrations");
      } finally {
        setIntegrationsLoading(false);
      }
    };

    loadIntegrations();
  }, []);

  const mapSyncStatus = (
    status?: string | null,
    lastSyncedAt?: string | null
  ): IntegrationSyncStatus => {
    if (!status && !lastSyncedAt) return "never";
    if (status === "error") return "error";
    return "success";
  };

  const formatDate = (value?: string | null) => {
    if (!value) return undefined;
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return undefined;
    return date.toLocaleString();
  };

  const handleAddIntegration = () => {
    setNewConnectorType(undefined);
    setNewName("");
    setNewAuthType(undefined);
    setNewConfig({});
    setAddError(null);
    setAddModalOpen(true);
  };

  const validateNew = (): string | null => {
    if (!newConnectorType) return "Connector type is required";
    if (!newAuthType) return "Authentication type is required";
    for (const field of newFields) {
      if (field.required && !newConfig[field.key]) {
        return `${field.label} is required`;
      }
    }
    if (newConnectorType === "jira") {
      const hasProject = (newConfig.project_key || "").trim().length > 0;
      const hasJql = (newConfig.jql || "").trim().length > 0;
      if (!hasProject && !hasJql) {
        return "Provide either a Project Key or a custom JQL query";
      }
    }
    return null;
  };

  const handleAddModalSave = async () => {
    const err = validateNew();
    if (err) {
      setAddError(err);
      return;
    }
    const connectorLabel =
      CONNECTOR_TYPES.find((c) => c.value === newConnectorType)?.label ?? newConnectorType!;
    const serviceName = newName.trim() || connectorLabel;

    setAddError(null);
    setIsAdding(true);
    try {
      const created = await createIntegration({
        service_name: serviceName,
        connector_type: newConnectorType!,
        auth_type: newAuthType!,
        config: newConfig,
        is_active: true,
      });
      if (!created) {
        setAddError("Failed to add integration");
        return;
      }
      setIntegrations((prev) => [...prev, created]);
      setAddModalOpen(false);
    } catch {
      setAddError("Failed to add integration");
    } finally {
      setIsAdding(false);
    }
  };

  const handleIntegrationSave = async (
    payload: IntegrationPayload & { id?: string; isNew?: boolean }
  ) => {
    const { id, isNew, ...body } = payload;
    setIntegrationsError(null);

    if (isNew) {
      const created = await createIntegration(body);
      if (!created) {
        setIntegrationsError("Failed to add integration");
        throw new Error("Failed to add integration");
      }
      setIntegrations((prev) => prev.map((item) => (item.id === id ? { ...created } : item)));
      return;
    }

    if (!id) {
      setIntegrationsError("Integration ID missing for update");
      throw new Error("Integration ID missing for update");
    }

    const updated = await updateIntegration(id, body);
    if (!updated) {
      setIntegrationsError("Failed to update integration");
      throw new Error("Failed to update integration");
    }

    setIntegrations((prev) => prev.map((item) => (item.id === id ? { ...updated } : item)));
  };

  const handleIntegrationDelete = async (id?: string, isNew?: boolean) => {
    if (!id) return;
    if (isNew) {
      setIntegrations((prev) => prev.filter((item) => item.id !== id));
      return;
    }

    const deleted = await deleteIntegration(id);
    if (!deleted) {
      setIntegrationsError("Failed to delete integration");
      return;
    }

    setIntegrations((prev) => prev.filter((item) => item.id !== id));
  };

  const handleIntegrationSync = async (
    id: string,
    callbacks: {
      onProgress: (msg: string, batch?: number, total?: number, incidents?: number) => void;
      onDone: () => void;
      onError: (msg: string) => void;
    }
  ) => {
    if (!id) return;

    await syncIntegration(id, {
      onProgress: (evt) => {
        callbacks.onProgress(
          evt.message,
          evt.batch,
          evt.totalBatches,
          evt.totalIncidents
        );
      },
      onComplete: (evt) => {
        if (evt.success && evt.integration) {
          setIntegrations((prev) =>
            prev.map((item) =>
              item.id === id ? { ...evt.integration! } : item
            )
          );
        }
        callbacks.onDone();
      },
      onError: (msg) => {
        callbacks.onError(msg);
      },
    });
  };

  if (integrationsLoading) {
    return (
      <div className="space-y-6">
        <SettingsHeader
          title="Integrations"
          description="Integrate with external platforms to sync data automatically."
        />
        <SkeletonIntegrations count={2} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <SettingsHeader
        title="Integrations"
        description="Integrate with external platforms to sync data automatically."
      />

      <div className="flex flex-col gap-3">
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 w-full justify-between">
          <span className="flex flex-row items-center gap-1">
            <span className="text-sm md:text-medium text-text-primary flex-1">
              Manage integrations with external data sources
            </span>
            <InfoHint text="Connect external platforms like ServiceNow or Jira to automatically sync incident data into the knowledge base." />
          </span>
          {canCreate && (
            <Button
              variant="primary"
              className="font-semibold text-xs px-4 py-1 transition-colors duration-200 rounded-md cursor-pointer w-full sm:w-auto"
              onClick={handleAddIntegration}
            >
              Add
            </Button>
          )}
        </div>
        <div className="flex flex-col gap-3">
          {integrationsError ? (
            <span className="text-sm text-danger-text ">{integrationsError}</span>
          ) : null}

          {!integrationsLoading && !integrationsError && integrations.length === 0 ? (
            <span className="text-sm text-text-secondary">No integrations configured yet.</span>
          ) : null}

          {integrations.map((integration) => (
            <IntegrationControl
              key={integration.id}
              id={integration.id}
              serviceName={integration.service_name}
              connectorType={integration.connector_type}
              enabled={integration.is_active}
              syncStatus={mapSyncStatus(
                integration.last_sync_status,
                integration.last_synced_at
              )}
              lastSyncedAt={formatDate(integration.last_synced_at)}
              lastError={integration.last_sync_error || undefined}
              authType={integration.auth_type}
              config={integration.config}
              configuredSecrets={integration.configured_secrets}
              isNew={integration.isNew}
              onSave={(integration.isNew ? canCreate : canEdit) ? handleIntegrationSave : undefined}
              onDelete={(integration.isNew || canDelete) ? handleIntegrationDelete : undefined}
              onSync={canSync ? handleIntegrationSync : undefined}
              readOnly={!integration.isNew && !canEdit}
            />
          ))}
        </div>
      </div>

      <Modal
        isOpen={addModalOpen}
        onClose={() => setAddModalOpen(false)}
        title="Add Integration"
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setAddModalOpen(false)} disabled={isAdding}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleAddModalSave} disabled={isAdding}>
              {isAdding ? "Saving..." : "Save"}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium">Connector Type <span className="text-danger-text">*</span></label>
            <Dropdown
              className="block w-full"
              options={connectorOptions}
              value={newConnectorType}
              onChange={(value) => {
                const next = value as ConnectorType | undefined;
                setNewConnectorType(next);
                const label = CONNECTOR_TYPES.find((c) => c.value === next)?.label ?? "";
                setNewName(label);
                setNewAuthType(undefined);
                setNewConfig({});
                setAddError(null);
              }}
            />
          </div>

          {newConnectorType && (
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium">Display Name</label>
              <InputBox
                value={newName}
                placeholder={CONNECTOR_TYPES.find((c) => c.value === newConnectorType)?.label ?? "Integration name"}
                variant="primary"
                onChange={(value) => setNewName(value)}
              />
              <span className="text-xs text-text-secondary">Optional — defaults to connector type name</span>
            </div>
          )}

          {newConnectorType && (
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium">Authentication Type <span className="text-danger-text">*</span></label>
              <Dropdown
                className="block w-full"
                options={newAuthOptions}
                value={newAuthType}
                onChange={(value) => {
                  setNewAuthType(value as AuthType | undefined);
                  setNewConfig({});
                  setAddError(null);
                }}
              />
            </div>
          )}

          {newAuthType && newFields.length > 0 && (
            <div className="flex flex-col gap-3">
              <label className="text-sm font-medium">Configuration</label>
              {newFields.map((field) => (
                <div key={field.key} className="flex flex-col gap-1">
                  <label className="text-xs font-medium">
                    {field.label}
                    {field.required && <span className="text-danger-text"> *</span>}
                  </label>
                  <InputBox
                    value={String(newConfig[field.key] || "")}
                    placeholder={field.placeholder || field.label}
                    type={field.type === "password" ? "password" : "text"}
                    variant={field.type === "textarea" ? "multiline" : "primary"}
                    onChange={(value) =>
                      setNewConfig((prev) => ({ ...prev, [field.key]: value }))
                    }
                  />
                  {field.help && (
                    <span className="text-[11px] text-text-secondary">{field.help}</span>
                  )}
                </div>
              ))}
            </div>
          )}

          {addError && <span className="text-xs text-danger-text">{addError}</span>}
        </div>
      </Modal>
    </div>
  );
};

export default IntegrationsPage;

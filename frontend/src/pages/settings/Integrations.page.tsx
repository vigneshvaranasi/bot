import { useEffect, useState } from "react";
import SettingsHeader from "../../components/settings/SettingsHeader";
import { Button } from "../../components/ui/Button";
import IntegrationControl from "../../components/IntegrationControl";
import InfoHint from "../../components/ui/InfoHint";
import {
  fetchIntegrations,
  createIntegration,
  updateIntegration,
  deleteIntegration,
  syncIntegration,
  type IntegrationPayload,
} from "../../handlers/integrationHandlers";
import { type Integration, type IntegrationSyncStatus } from "../../types/Integrations";
import { SkeletonIntegrations } from "../../components/ui/Skeleton";
import { usePermissions } from "../../hooks/usePermissions";
import { PERMISSIONS } from "../../types/Permission";

const IntegrationsPage = () => {
  const { hasPermission } = usePermissions();
  const canCreate = hasPermission(PERMISSIONS.INTEGRATION_CREATE);
  const canEdit = hasPermission(PERMISSIONS.INTEGRATION_EDIT);
  const canDelete = hasPermission(PERMISSIONS.INTEGRATION_DELETE);
  const canSync = hasPermission(PERMISSIONS.INTEGRATION_SYNC);
  type IntegrationItem = Omit<Integration, "auth_type"> & {
    auth_type?: Integration["auth_type"];
    isNew?: boolean;
  };

  const [integrations, setIntegrations] = useState<IntegrationItem[]>([]);
  const [integrationsLoading, setIntegrationsLoading] = useState(false);
  const [integrationsError, setIntegrationsError] = useState<string | null>(null);

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
    const tempId = `new-${Date.now()}`;
    setIntegrations((prev) => [
      ...prev,
      {
        id: tempId,
        service_name: "",
        auth_type: undefined,
        config: {},
        is_active: true,
        last_sync_error: null,
        last_synced_at: null,
        last_sync_status: null,
        updated_at: undefined,
        isNew: true,
      },
    ]);
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

  const handleIntegrationSync = async (id?: string) => {
    if (!id) return;

    const updated = await syncIntegration(id);
    if (!updated) {
      setIntegrationsError("Failed to sync integration");
      return;
    }

    setIntegrations((prev) => prev.map((item) => (item.id === id ? { ...updated } : item)));
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
            <span className="text-sm md:text-medium text-black flex-1">
              Manage integrations with external data sources
            </span>
            <InfoHint
              text="Integrations with platforms like ServiceNow or Jira allow continuous data synchronization."
              position="top"
              gap={0.3}
            />
          </span>
          {canCreate && (
            <Button
              variant="primary"
              className="font-semibold text-xs px-4 py-1 transition-colors duration-200 text-white rounded-md cursor-pointer w-full sm:w-auto"
              onClick={handleAddIntegration}
            >
              Add
            </Button>
          )}
        </div>
        <div className="flex flex-col gap-3">
          {integrationsError ? (
            <span className="text-sm text-red-500 ">{integrationsError}</span>
          ) : null}

          {!integrationsLoading && !integrationsError && integrations.length === 0 ? (
            <span className="text-sm text-gray-600">No integrations configured yet.</span>
          ) : null}

          {integrations.map((integration) => (
            <IntegrationControl
              key={integration.id}
              id={integration.id}
              serviceName={integration.service_name}
              enabled={integration.is_active}
              syncStatus={mapSyncStatus(
                integration.last_sync_status,
                integration.last_synced_at
              )}
              lastSyncedAt={formatDate(integration.last_synced_at)}
              lastError={integration.last_sync_error || undefined}
              authType={integration.auth_type}
              config={integration.config}
              isNew={integration.isNew}
              onSave={(integration.isNew ? canCreate : canEdit) ? handleIntegrationSave : undefined}
              onDelete={(integration.isNew || canDelete) ? handleIntegrationDelete : undefined}
              onSync={canSync ? handleIntegrationSync : undefined}
              readOnly={!integration.isNew && !canEdit}
            />
          ))}
        </div>
      </div>
    </div>
  );
};

export default IntegrationsPage;

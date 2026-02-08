import { useEffect, useState } from "react";
import SettingsHeader from "../../components/settings/SettingsHeader";
import { Button } from "../../components/ui/Button";
import { ConfigurableTable } from "../../components/ui/Table";
import { fetchIntegrations } from "../../handlers/integrationHandlers";
import { fetchIncidentLogs, type IncidentLog } from "../../handlers/knowledgeBaseHandlers";
import type { Integration } from "../../types/Integrations";
import { SkeletonAudit } from "../../components/ui/Skeleton";

const KnowledgeBasePage = () => {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [logs, setLogs] = useState<IncidentLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadIntegrations = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Fetch integrations
      const result = await fetchIntegrations();
      if (result) {
        // Filter only ServiceNow integrations that have been synced
        const servicenowIntegrations = result.filter(
          (i) => i.service_name === "snow" && i.last_synced_at
        );
        setIntegrations(servicenowIntegrations);
      } else {
        setError("Failed to load sync history");
      }
      
      // Fetch incident logs
      const logsResult = await fetchIncidentLogs(50);
      if (logsResult) {
        setLogs(logsResult);
      }
    } catch (err) {
      console.error("Error loading integrations:", err);
      setError("Failed to load sync history");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadIntegrations();
  }, []);

  const columns = [
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
        item.last_synced_at
          ? new Date(item.last_synced_at).toLocaleString()
          : "Never",
      searchable: false,
    },
    {
      header: "Status",
      headerClassName: "font-medium text-gray-700 text-xs md:text-sm sticky top-0 bg-gray-50 z-10 border-b border-gray-200",
      className: "text-xs md:text-sm py-3",
      render: (item: Integration) => {
        const status = item.last_sync_status || "never";
        const colors = {
          success: "bg-green-100 text-green-800",
          error: "bg-red-100 text-red-800",
          never: "bg-gray-100 text-gray-800",
        };
        return (
          <span
            className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${
              colors[status as keyof typeof colors] || colors.never
            }`}
          >
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

  if (loading) {
    return (
      <div className="space-y-6">
        <SettingsHeader
          title="Knowledge Base"
          description="ServiceNow incident sync history"
        />
        <SkeletonAudit />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <SettingsHeader
        title="Knowledge Base"
        description="View ServiceNow incident synchronization history"
      />

      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 p-4">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}

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
            <Button onClick={loadIntegrations} variant="secondary" className="text-xs px-3 py-1">
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

      {/* Sync History */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-medium text-gray-900">Sync History</h3>
            <p className="text-xs text-gray-500 mt-1">
              Incidents are automatically synced to the vector database when integrations are updated
            </p>
          </div>
          <Button onClick={loadIntegrations} variant="secondary" className="text-xs px-3 py-1">
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
          <ConfigurableTable
            data={integrations}
            columns={columns}
          />
        )}
      </div>
    </div>
  );
};

export default KnowledgeBasePage;


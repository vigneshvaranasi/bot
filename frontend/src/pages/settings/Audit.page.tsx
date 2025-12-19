import SettingsHeader from "../../components/settings/SettingsHeader";

const AuditPage = () => {
  return (
    <div className="space-y-4">
      <SettingsHeader
        title="Audit & Logs"
        description="Review configuration change history. Implement server-backed table with filters and export."
      />
      <div className="border border-dashed border-gray-300 rounded-lg p-6 text-sm text-gray-600 bg-gray-50">
        Audit log UI placeholder
      </div>
    </div>
  );
};

export default AuditPage;

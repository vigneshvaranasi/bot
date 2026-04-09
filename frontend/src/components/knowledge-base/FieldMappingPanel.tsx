import { useState, useEffect } from "react";
import { Button } from "../ui/Button";

const TARGET_FIELDS = [
  "incident_id",
  "title",
  "description",
  "action_taken",
  "opened_at",
  "updated_at",
  "impacted_application",
  "root_cause",
  "mitigation",
  "accountable_party",
  "source_system",
  "repeat_incident",
];

type Props = {
  fileFields: Record<string, string[]>; // {filename: [fields]}
  onApply: (mapping: Record<string, string>) => void;
  onCancel: () => void;
  isLoading?: boolean;
};

const FieldMappingPanel = ({ fileFields, onApply, onCancel, isLoading }: Props) => {
  const [mapping, setMapping] = useState<Record<string, string>>({});

  // Only show files that have at least one unmapped field
  const filesNeedingMapping = Object.entries(fileFields).filter(([, fields]) =>
    fields.some((f) => !TARGET_FIELDS.includes(f))
  );

  // Auto-match fields with identical names across all files
  useEffect(() => {
    const autoMap: Record<string, string> = {};
    for (const fields of Object.values(fileFields)) {
      for (const src of fields) {
        const lower = src.toLowerCase().replace(/[\s-]/g, "_");
        if (TARGET_FIELDS.includes(lower)) {
          autoMap[src] = lower;
        }
      }
    }
    setMapping(autoMap);
  }, [fileFields]);

  const handleChange = (sourceField: string, targetField: string) => {
    setMapping((prev) => {
      const next = { ...prev };
      if (targetField) {
        next[sourceField] = targetField;
      } else {
        delete next[sourceField];
      }
      return next;
    });
  };

  return (
    <div className="space-y-4">
      <div className="p-3 rounded-lg border border-info-border bg-info-subtle">
        <p className="text-xs text-info-text">
          Map your source fields to the expected incident schema fields.
          Fields with matching names have been auto-mapped. Only files with unmapped fields are shown.
        </p>
      </div>

      {filesNeedingMapping.length === 0 && (
        <div className="p-4 text-center text-sm text-text-secondary">
          All fields across all files are already mapped. Click "Apply & Re-validate" to proceed.
        </div>
      )}

      {filesNeedingMapping.map(([filename, fields]) => (
        <div key={filename} className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-surface-tertiary text-text-secondary font-mono">
              {filename}
            </span>
            <span className="text-xs text-text-tertiary">{fields.length} fields</span>
          </div>

          <div className="rounded-lg border border-border-default overflow-hidden">
            <table className="min-w-full text-sm">
              <thead className="bg-surface-secondary">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-text-secondary border-b border-border-default">
                    Source Field
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-text-secondary border-b border-border-default">
                    Target Field
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-text-secondary border-b border-border-default w-16">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-default">
                {fields.map((src) => {
                  const isAutoMapped = TARGET_FIELDS.includes(src);
                  const isMapped = !!mapping[src];
                  return (
                    <tr key={src} className={isAutoMapped ? "bg-success-subtle/50" : "hover:bg-surface-secondary"}>
                      <td className="px-4 py-2 text-xs text-text-primary font-mono">{src}</td>
                      <td className="px-4 py-2">
                        {isAutoMapped ? (
                          <span className="text-xs text-success-text font-mono">{src}</span>
                        ) : (
                          <select
                            value={mapping[src] || ""}
                            onChange={(e) => handleChange(src, e.target.value)}
                            className="w-full text-xs border border-border-strong rounded px-2 py-1 bg-surface-primary text-text-primary focus:outline-none focus:ring-1 focus:ring-accent-blue"
                          >
                            <option value="">-- skip --</option>
                            {TARGET_FIELDS.map((t) => (
                              <option key={t} value={t}>
                                {t}
                              </option>
                            ))}
                          </select>
                        )}
                      </td>
                      <td className="px-4 py-2 text-center">
                        {isAutoMapped || isMapped ? (
                          <span className="inline-block w-2 h-2 rounded-full bg-success" title="Mapped" />
                        ) : (
                          <span className="inline-block w-2 h-2 rounded-full bg-warning" title="Unmapped" />
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ))}

      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onCancel} className="text-xs">
          Cancel
        </Button>
        <Button
          variant="primary"
          onClick={() => onApply(mapping)}
          disabled={isLoading || Object.keys(mapping).length === 0}
          className="text-xs"
        >
          {isLoading ? "Applying..." : "Apply & Re-validate"}
        </Button>
      </div>
    </div>
  );
};

export default FieldMappingPanel;

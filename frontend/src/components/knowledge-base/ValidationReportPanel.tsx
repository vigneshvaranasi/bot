import type { ValidationReport } from "../../types/KnowledgeBase";
import { Button } from "../ui/Button";

type Props = {
  report: ValidationReport;
  onMapFields: () => void;
  onConfirmIngest: () => void;
};

const ValidationReportPanel = ({ report, onMapFields, onConfirmIngest }: Props) => {
  const hasErrors = report.error_count > 0;

  return (
    <div className="space-y-4">
      {/* Summary bar */}
      <div className="flex items-center gap-4 p-3 rounded-lg border border-border-default bg-surface-secondary">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center px-2.5 py-1 rounded text-xs font-medium bg-success-subtle text-success-text">
            {report.valid_count} valid
          </span>
          {hasErrors && (
            <span className="inline-flex items-center px-2.5 py-1 rounded text-xs font-medium bg-danger-subtle text-danger-text">
              {report.error_count} errors
            </span>
          )}
        </div>
        <span className="text-xs text-text-secondary">
          {report.total_records} total records
        </span>
      </div>

      {/* Error list */}
      {hasErrors && (
        <div className="rounded-lg border border-danger bg-danger-subtle overflow-hidden">
          <div className="p-3 border-b border-danger">
            <h4 className="text-sm font-medium text-danger-text">Validation Errors</h4>
          </div>
          <div className="max-h-[200px] overflow-y-auto divide-y divide-danger-subtle">
            {report.errors.map((err, idx) => (
              <div key={idx} className="px-3 py-2 text-xs text-danger-text">
                <span className="font-mono bg-danger-subtle px-1 rounded">[{err.file}]</span>
                {err.row != null && <span className="ml-1">Row {err.row}:</span>}
                <span className="ml-1">
                  Field "<strong>{err.field}</strong>" &mdash; {err.message}
                </span>
                {err.value && (
                  <span className="ml-1 text-danger-text">(value: "{err.value}")</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Preview table */}
      {report.preview.length > 0 && (
        <div className="rounded-lg border border-border-default overflow-hidden">
          <div className="p-3 border-b border-border-default">
            <h4 className="text-sm font-medium text-text-primary">
              Preview (first {report.preview.length} records)
            </h4>
          </div>
          <div className="overflow-x-auto max-h-[250px]">
            <table className="min-w-full text-xs">
              <thead className="bg-surface-secondary sticky top-0">
                <tr>
                  {Object.keys(report.preview[0]).map((key) => (
                    <th key={key} className="px-3 py-2 text-left text-text-secondary font-medium border-b border-border-default">
                      {key}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border-default">
                {report.preview.map((row, rIdx) => (
                  <tr key={rIdx} className="hover:bg-surface-secondary">
                    {Object.values(row).map((val, cIdx) => (
                      <td key={cIdx} className="px-3 py-2 text-text-secondary max-w-[200px] truncate">
                        {String(val ?? "")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex justify-end gap-2">
        {hasErrors && (
          <Button variant="secondary" onClick={onMapFields} className="text-xs">
            Map Fields
          </Button>
        )}
        <Button
          variant="primary"
          onClick={onConfirmIngest}
          disabled={report.valid_count === 0}
          className="text-xs"
        >
          Confirm &amp; Ingest ({report.valid_count} records)
        </Button>
      </div>
    </div>
  );
};

export default ValidationReportPanel;

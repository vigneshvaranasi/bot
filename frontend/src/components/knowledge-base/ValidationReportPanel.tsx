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
      <div className="flex items-center gap-4 p-3 rounded-lg border border-gray-200 bg-gray-50">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center px-2.5 py-1 rounded text-xs font-medium bg-green-100 text-green-800">
            {report.valid_count} valid
          </span>
          {hasErrors && (
            <span className="inline-flex items-center px-2.5 py-1 rounded text-xs font-medium bg-red-100 text-red-800">
              {report.error_count} errors
            </span>
          )}
        </div>
        <span className="text-xs text-gray-500">
          {report.total_records} total records
        </span>
      </div>

      {/* Error list */}
      {hasErrors && (
        <div className="rounded-lg border border-red-200 bg-red-50 overflow-hidden">
          <div className="p-3 border-b border-red-200">
            <h4 className="text-sm font-medium text-red-800">Validation Errors</h4>
          </div>
          <div className="max-h-[200px] overflow-y-auto divide-y divide-red-100">
            {report.errors.map((err, idx) => (
              <div key={idx} className="px-3 py-2 text-xs text-red-700">
                <span className="font-mono bg-red-100 px-1 rounded">[{err.file}]</span>
                {err.row != null && <span className="ml-1">Row {err.row}:</span>}
                <span className="ml-1">
                  Field "<strong>{err.field}</strong>" &mdash; {err.message}
                </span>
                {err.value && (
                  <span className="ml-1 text-red-500">(value: "{err.value}")</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Preview table */}
      {report.preview.length > 0 && (
        <div className="rounded-lg border border-gray-200 overflow-hidden">
          <div className="p-3 border-b border-gray-200">
            <h4 className="text-sm font-medium text-gray-900">
              Preview (first {report.preview.length} records)
            </h4>
          </div>
          <div className="overflow-x-auto max-h-[250px]">
            <table className="min-w-full text-xs">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  {Object.keys(report.preview[0]).map((key) => (
                    <th key={key} className="px-3 py-2 text-left text-gray-600 font-medium border-b border-gray-200">
                      {key}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {report.preview.map((row, rIdx) => (
                  <tr key={rIdx} className="hover:bg-gray-50">
                    {Object.values(row).map((val, cIdx) => (
                      <td key={cIdx} className="px-3 py-2 text-gray-700 max-w-[200px] truncate">
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

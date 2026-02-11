export interface ValidationError {
  file: string;
  row?: number;
  field: string;
  message: string;
  value?: string;
}

export interface ValidationReport {
  session_id: string;
  status: string;
  total_records: number;
  valid_count: number;
  error_count: number;
  errors: ValidationError[];
  preview: Record<string, unknown>[];
  file_fields?: Record<string, string[]>; // {filename: [fields in that file]}
}

export interface DatasetVersion {
  id: string;
  version_number: number;
  collection_name: string;
  status: string;
  is_active: boolean;
  incident_count: number;
  file_metadata: { filename: string; size: number; row_count: number }[];
  uploader_email?: string;
  snapshot_name?: string;
  notes?: string;
  source: string;
  activated_at?: string;
  created_at: string;
  updated_at: string;
}

export interface DatasetVersionList {
  versions: DatasetVersion[];
  total: number;
  active_version_id?: string;
}

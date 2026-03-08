// Model type is now flexible to support dynamic models from providers
export type Model = string;

export type SettingSegment = "aiml" | "auth";

// Change type for audit trail
export type ChangeType = "create" | "update" | "rollback";

// Describes a single field change
export type ChangeDescription = {
  field: string;
  field_label: string;
  old_value: string | null;
  new_value: string | null;
  segment: SettingSegment;
};

export type Settings = {
  id?: string;
  user_id?: string;
  deny_words: string;
  model: Model;
  temperature: string;
  langfuse_enabled: boolean;
  allow_user_model_selection: boolean;
  auth_google_enabled: boolean;
  auth_github_enabled: boolean;
  auth_microsoft_enabled: boolean;
  auth_local_enabled: boolean;
  provider_id?: string | null;  // LLM provider selection
  created_at?: string;
  updated_at?: string;
}

export type AiMlSettings = {
  model: Model;
  temperature: string;
  deny_words: string;
  langfuse_enabled: boolean;
  langfuse_secret_key?: string;
  langfuse_public_key?: string | null;
  langfuse_base_url?: string | null;
  has_langfuse_secret_key?: boolean;
  allow_user_model_selection: boolean;
  provider_id?: string | null;  // LLM provider selection
}

export type AuthSettings = {
  auth_google_enabled: boolean;
  auth_github_enabled: boolean;
  auth_microsoft_enabled: boolean;
  auth_local_enabled: boolean;
}

export type SegmentSettingResponse<T> = {
  segment: SettingSegment;
  settings: T;
  version_id: string | null;  // null when returning defaults (no settings in DB yet)
  updated_at: string | null;  // null when returning defaults
}

export type SettingHistoryItem = {
  id: string;
  user_id: string;
  user_email?: string | null;
  created_at: string;
  updated_at: string;
  // Audit trail fields
  change_type: ChangeType;
  source_version_id?: string | null;
  target_version_id?: string | null;
  change_reason?: string | null;
  // Computed changes compared to previous version
  changes: ChangeDescription[];
  // Settings values
  model: Model;
  temperature: string;
  deny_words: string;
  langfuse_enabled: boolean;
  langfuse_public_key?: string | null;
  langfuse_base_url?: string | null;
  has_langfuse_secret_key?: boolean;
  allow_user_model_selection: boolean;
  auth_google_enabled: boolean;
  auth_github_enabled: boolean;
  auth_microsoft_enabled: boolean;
  auth_local_enabled: boolean;
  provider_id?: string | null;
}

export type SettingHistoryResponse = {
  history: SettingHistoryItem[];
  total: number;
}

export type FileRecord = {
  fileName: string;
  fileType: string;
  size: string;
  lastUpdated: string;
  id: string;
}

export type DenyWordRecord = {
  id: string;
  word: string;
}

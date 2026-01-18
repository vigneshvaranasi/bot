// Model type is now flexible to support dynamic models from providers
export type Model = string;

export type SettingSegment = "aiml" | "auth";

export type Settings = {
  id?: string;
  user_id?: string;
  deny_words: string;
  model: Model;
  temperature: string;
  langfuse_enabled: boolean;
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
  version_id: string;
  updated_at: string;
}

export type SettingHistoryItem = {
  id: string;
  user_id: string;
  created_at: string;
  updated_at: string;
  model: Model;
  temperature: string;
  deny_words: string;
  langfuse_enabled: boolean;
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

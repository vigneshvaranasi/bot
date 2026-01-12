/**
 * Shared TypeScript types for the frontend application.
 * These types mirror the backend API schemas.
 */

// ============================================================================
// Chat & Message Types
// ============================================================================

/**
 * A single chat message in the conversation.
 */
export interface ChatMessage {
  id: string;
  userMessage: string;
  botMessage: string;
  streaming?: boolean;
  _streamBuffer?: string;
  _finalAnswerStarted?: boolean;
  _finalAnswerDone?: boolean;
  responseMetrics?: StreamMetrics;
}

/**
 * A chat with all its messages (used for current chat state).
 */
export interface Chat {
  chatId: string;
  allMessages: ChatMessage[];
}

/**
 * Chat list item from API (for sidebar display).
 */
export interface ChatListItem {
  id: string;
  title: string;
  updated_at: string;
}

/**
 * Response from getAllMyChats API.
 */
export interface ChatsListResponse {
  chats: ChatListItem[];
}

// ============================================================================
// Stream Metrics Types
// ============================================================================

/**
 * Metrics for streaming response performance.
 */
export interface StreamMetrics {
  timeToFirstToken?: number;
  totalResponseTime: number;
}

// ============================================================================
// Settings Types
// ============================================================================

/**
 * Available LLM model options.
 */
export type ModelEnum =
  | "gemma3:1b"
  | "gemma3:4b"
  | "gemini-2.0-flash"
  | "gemini-2.5-flash"
  | "gemini-2.0-flash-lite-001"
  | "gemini-2.5-pro"
  | "gpt-oss:20b";

/**
 * Settings response from API.
 */
export interface SettingResponse {
  id: string;
  user_id: string;
  deny_words: string;
  model: ModelEnum;
  temperature: string;
  langfuse_enabled: boolean;
  auth_google_enabled: boolean;
  auth_github_enabled: boolean;
  auth_microsoft_enabled: boolean;
  auth_local_enabled: boolean;
  updated_at: string;
}

/**
 * Settings update payload.
 */
export interface SettingUpdate {
  deny_words?: string;
  model?: ModelEnum;
  temperature?: string;
  langfuse_enabled?: boolean;
  auth_google_enabled?: boolean;
  auth_github_enabled?: boolean;
  auth_microsoft_enabled?: boolean;
  auth_local_enabled?: boolean;
}

// ============================================================================
// User & Auth Types
// ============================================================================

/**
 * User information stored in auth context.
 */
export interface User {
  id: string;
  email: string;
  role: string;
  is_active?: boolean;
  auth_identities?: string[];
}

/**
 * Token response from login/signup.
 */
export interface TokenResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  email: string | null;
  role: string;
}

/**
 * User response from API.
 */
export interface UserResponse {
  id: string;
  email: string | null;
  is_active: boolean;
  role: string;
  auth_identities: string[];
}

// ============================================================================
// Integration Types
// ============================================================================

/**
 * Authentication type for integrations.
 */
export type AuthType = "basic_auth" | "api_token" | "oauth2";

/**
 * Integration configuration.
 */
export interface Integration {
  id: string;
  service_name: string;
  auth_type: AuthType;
  config: Record<string, string>;
  is_active: boolean;
  last_synced_at?: string | null;
  last_sync_status?: string | null;
  last_sync_error?: string | null;
  updated_at: string;
}

// ============================================================================
// Role Types
// ============================================================================

/**
 * User role.
 */
export interface Role {
  id: string;
  name: string;
}

// ============================================================================
// Re-export existing types for backwards compatibility
// ============================================================================

export type { ChatInSidebar } from "./Chats";
export type { Settings, FileRecord, DenyWordRecord, Model } from "./Settings";

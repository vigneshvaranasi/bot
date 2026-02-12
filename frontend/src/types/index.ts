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
  statusMessage?: string;
  _streamBuffer?: string;
  _finalAnswerStarted?: boolean;
  _finalAnswerDone?: boolean;
  responseMetrics?: StreamMetrics;
  feedback?: 'positive' | 'negative' | null;
  feedbackId?: string;
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
 * Settings response from API.
 */
export interface SettingResponse {
  id: string;
  user_id: string;
  deny_words: string;
  model: string;
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
  model?: string;
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

export type FeedbackType = 'positive' | 'negative';

export interface FeedbackCreate {
  message_id: string;
  feedback_type: FeedbackType;
  reason?: string;
}

export interface FeedbackResponse {
  id: string;
  message_id: string;
  user_id: string | null;
  feedback_type: FeedbackType;
  reason: string | null;
  status: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
}

export interface FeedbackItem {
  id: string;
  message_id: string;
  user_id: string | null;
  user_email: string | null;
  feedback_type: FeedbackType;
  reason: string | null;
  status: string;
  reviewed_by: string | null;
  reviewer_email: string | null;
  reviewed_at: string | null;
  created_at: string;
  original_query: string;
  original_response: string;
  chat_id: string;
  has_golden_example: boolean;
  golden_example_id: string | null;
  golden_response: string | null;
}

export interface FeedbackStats {
  total_feedback: number;
  positive_count: number;
  negative_count: number;
  pending_count: number;
  auto_approved_count: number;
  reviewed_count: number;
  dismissed_count: number;
  golden_examples_count: number;
}

export interface FeedbackSettings {
  auto_approve_positive: boolean;
  auto_approve_negative: boolean;
  require_reason_positive: boolean;
  require_reason_negative: boolean;
}

// ============================================================================
// Re-export existing types for backwards compatibility
// ============================================================================

export type { ChatInSidebar } from "./Chats";
export type { Settings, FileRecord, DenyWordRecord, Model } from "./Settings";

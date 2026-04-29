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
  stopped?: boolean;
  statusMessage?: string;
  _streamBuffer?: string;
  _finalAnswerStarted?: boolean;
  _finalAnswerDone?: boolean;
  _fenceStripped?: boolean;
  _fenceCleanDone?: boolean;
  responseMetrics?: StreamMetrics;
  feedback?: 'positive' | 'negative' | null;
  feedbackId?: string;
  sentAt?: string | null;
  respondedAt?: string | null;
  modelId?: string | null;
  providerType?: string | null;
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
  modelId?: string | null;
  providerType?: string | null;
}

// ============================================================================
// Feedback Types
// ============================================================================

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

export type QueryType = 'static' | 'temporal';

export interface FeedbackItem {
  id: string;
  message_id: string;
  user_id: string | null;
  user_email: string | null;
  feedback_type: FeedbackType;
  reason: string | null;
  status: string;
  ai_validated: string | null;
  ai_reason: string | null;
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
  query_type?: QueryType;
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
  require_reason_positive: boolean;
  require_reason_negative: boolean;
  auto_approve_by_ai: boolean;
}

// ============================================================================
// Re-export existing types for backwards compatibility
// ============================================================================

export type { ChatInSidebar } from "./Chats";
export type { Settings, FileRecord, DenyWordRecord, Model } from "./Settings";

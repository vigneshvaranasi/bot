import type { FeedbackCreate, FeedbackResponse, FeedbackType, FeedbackItem, FeedbackStats, FeedbackSettings } from '../types';
import { BE_URL } from '../config/config';
export async function submitFeedback(
  token: string,
  messageId: string,
  feedbackType: FeedbackType,
  reason?: string
): Promise<FeedbackResponse> {
  const payload: FeedbackCreate = {
    message_id: messageId,
    feedback_type: feedbackType,
    reason: reason || undefined,
  };

  const response = await fetch(`${BE_URL}/feedback/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to submit feedback' }));
    throw new Error(error.detail || 'Failed to submit feedback');
  }

  return response.json();
}

export async function getFeedbackForMessage(
  token: string,
  messageId: string
): Promise<FeedbackResponse | null> {
  const response = await fetch(`${BE_URL}/feedback/message/${messageId}`, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    if (response.status === 404) {
      return null;
    }
    throw new Error('Failed to get feedback');
  }

  const data = await response.json();
  return data || null;
}

export async function getFeedbackForMessages(
  token: string,
  messageIds: string[]
): Promise<Map<string, FeedbackResponse>> {
  const feedbackMap = new Map<string, FeedbackResponse>();
  
  const promises = messageIds.map(async (messageId) => {
    try {
      const feedback = await getFeedbackForMessage(token, messageId);
      if (feedback) {
        feedbackMap.set(messageId, feedback);
      }
    } catch {
    }
  });

  await Promise.all(promises);
  return feedbackMap;
}

export async function fetchFeedbackList(
  token: string,
  limit: number,
  offset: number,
  status?: string,
  type?: string,
  search?: string
): Promise<{ items: FeedbackItem[]; total: number }> {
  const params = new URLSearchParams();
  params.append('limit', limit.toString());
  params.append('offset', offset.toString());
  if (status) params.append('status', status);
  if (type) params.append('type', type);
  if (search) params.append('search', search);

  const response = await fetch(`${BE_URL}/feedback/admin/list?${params}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  
  if (!response.ok) {
    throw new Error('Failed to fetch feedback list');
  }
  
  return response.json();
}

export async function fetchFeedbackStats(token: string): Promise<FeedbackStats> {
  const response = await fetch(`${BE_URL}/feedback/admin/stats`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  
  if (!response.ok) {
    throw new Error('Failed to fetch feedback stats');
  }
  
  return response.json();
}

export async function fetchFeedbackSettings(token: string): Promise<FeedbackSettings> {
  const response = await fetch(`${BE_URL}/feedback/admin/settings`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  
  if (!response.ok) {
    throw new Error('Failed to fetch feedback settings');
  }
  
  return response.json();
}

export async function updateFeedbackSettings(
  token: string,
  settings: Partial<FeedbackSettings>
): Promise<FeedbackSettings> {
  const response = await fetch(`${BE_URL}/feedback/admin/settings`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(settings),
  });
  
  if (!response.ok) {
    throw new Error('Failed to update feedback settings');
  }
  
  return response.json();
}

export async function resolveFeedback(
  token: string,
  feedbackId: string,
  goldenResponse?: string
): Promise<void> {
  const response = await fetch(`${BE_URL}/feedback/admin/${feedbackId}/resolve`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ golden_response: goldenResponse }),
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to resolve feedback' }));
    throw new Error(error.detail || 'Failed to resolve feedback');
  }
}

export async function dismissFeedback(
  token: string,
  feedbackId: string,
  reason?: string
): Promise<void> {
  const response = await fetch(`${BE_URL}/feedback/admin/${feedbackId}/dismiss`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ reason }),
  });
  
  if (!response.ok) {
    throw new Error('Failed to dismiss feedback');
  }
}

export async function deleteFeedback(token: string, feedbackId: string): Promise<void> {
  const response = await fetch(`${BE_URL}/feedback/admin/${feedbackId}`, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete feedback' }));
    throw new Error(error.detail || 'Failed to delete feedback');
  }
}

export async function restoreFeedback(token: string, feedbackId: string): Promise<void> {
  const response = await fetch(`${BE_URL}/feedback/admin/${feedbackId}/restore`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to restore feedback' }));
    throw new Error(error.detail || 'Failed to restore feedback');
  }
}

export async function updateGoldenExample(
  token: string,
  exampleId: string,
  goldenResponse: string
): Promise<void> {
  const response = await fetch(`${BE_URL}/feedback/golden-examples/${exampleId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ golden_response: goldenResponse }),
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update golden example' }));
    throw new Error(error.detail || 'Failed to update golden example');
  }
}

export interface GenerateResponseResult {
  generated_response: string;
  tool_calls_made: number;
  generation_time_ms: number;
  success: boolean;
  error?: string;
}

export async function generateGoldenResponse(
  token: string,
  feedbackId: string
): Promise<GenerateResponseResult> {
  const response = await fetch(`${BE_URL}/feedback/admin/${feedbackId}/generate-response`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to generate response' }));
    throw new Error(error.detail || 'Failed to generate response');
  }
  
  return response.json();
}
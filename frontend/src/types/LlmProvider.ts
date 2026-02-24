/**
 * LLM Provider type definitions for the frontend.
 */

/**
 * Supported LLM provider types.
 */
export type ProviderType = 'anthropic' | 'openai' | 'google' | 'custom';

/**
 * Health check status values.
 */
export type HealthStatus = 'success' | 'error' | null;

/**
 * LLM Provider configuration stored in the database.
 */
export interface LlmProvider {
  id: string;
  name: string;
  provider_type: ProviderType;
  base_url: string | null;
  has_api_key: boolean;
  config: ProviderConfig;
  models: string[];
  is_active: boolean;
  is_default: boolean;
  last_health_check_at: string | null;
  last_health_check_status: HealthStatus;
  last_health_check_error: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * Provider-specific configuration options.
 */
export interface ProviderConfig {
  // Authentication type for custom providers
  auth_type?: 'none' | 'bearer' | 'api_key_header' | 'basic';
  // Custom header name for API key authentication
  auth_header_name?: string;
  // Organization ID for OpenAI
  organization_id?: string;
  // Whether this is an OpenAI-compatible API (vs Ollama-compatible)
  openai_compatible?: boolean;
  // Auto-discover models from the API
  auto_discover_models?: boolean;
  // Custom headers to send with requests
  custom_headers?: Record<string, string>;
}

/**
 * Payload for creating a new LLM provider.
 */
export interface LlmProviderCreate {
  name: string;
  provider_type: ProviderType;
  base_url?: string | null;
  api_key?: string | null;
  config?: ProviderConfig;
  models?: string[];
  is_active?: boolean;
  is_default?: boolean;
}

/**
 * Payload for updating an LLM provider.
 */
export interface LlmProviderUpdate {
  name?: string;
  base_url?: string | null;
  api_key?: string | null;
  config?: ProviderConfig;
  models?: string[];
  is_active?: boolean;
  is_default?: boolean;
}

/**
 * Response from provider list endpoint.
 */
export interface LlmProviderListResponse {
  providers: LlmProvider[];
  total: number;
}

/**
 * Health check result from test connection endpoint.
 */
export interface HealthCheckResult {
  success: boolean;
  provider_id: string;
  status: 'success' | 'error';
  message?: string;
  response_time_ms?: number;
}

/**
 * Available model for selection.
 */
export interface AvailableModel {
  provider_id: string;
  provider_name: string;
  provider_type: string;
  model_id: string;
  display_name: string;
  is_default_provider: boolean;
}

/**
 * Response from available models endpoint.
 */
export interface AvailableModelsResponse {
  models: AvailableModel[];
}

/**
 * Display labels for provider types.
 */
export const PROVIDER_LABELS: Record<ProviderType, string> = {
  anthropic: 'Anthropic (Claude)',
  openai: 'OpenAI (GPT)',
  google: 'Google (Gemini)',
  custom: 'Custom Provider',
};

/**
 * Provider type colors for badges.
 */
export const PROVIDER_COLORS: Record<ProviderType, string> = {
  anthropic: 'bg-orange-100 text-orange-800',
  openai: 'bg-green-100 text-green-800',
  google: 'bg-blue-100 text-blue-800',
  custom: 'bg-purple-100 text-purple-800',
};

/**
 * Form field configuration for each provider type.
 */
export interface ProviderFieldConfig {
  showApiKey: boolean;
  apiKeyRequired: boolean;
  showBaseUrl: boolean;
  baseUrlRequired: boolean;
  showAuthType: boolean;
  showOrganizationId: boolean;
  baseUrlPlaceholder: string;
  apiKeyPlaceholder: string;
}

export const PROVIDER_FIELDS: Record<ProviderType, ProviderFieldConfig> = {
  anthropic: {
    showApiKey: true,
    apiKeyRequired: true,
    showBaseUrl: true,
    baseUrlRequired: false,
    showAuthType: false,
    showOrganizationId: false,
    baseUrlPlaceholder: 'https://api.anthropic.com (optional, for proxies)',
    apiKeyPlaceholder: 'sk-ant-...',
  },
  openai: {
    showApiKey: true,
    apiKeyRequired: true,
    showBaseUrl: true,
    baseUrlRequired: false,
    showAuthType: false,
    showOrganizationId: true,
    baseUrlPlaceholder: 'https://api.openai.com (optional, for proxies)',
    apiKeyPlaceholder: 'sk-...',
  },
  google: {
    showApiKey: true,
    apiKeyRequired: true,
    showBaseUrl: false,
    baseUrlRequired: false,
    showAuthType: false,
    showOrganizationId: false,
    baseUrlPlaceholder: '',
    apiKeyPlaceholder: 'AI...',
  },
  custom: {
    showApiKey: true,
    apiKeyRequired: false,
    showBaseUrl: true,
    baseUrlRequired: true,
    showAuthType: true,
    showOrganizationId: false,
    baseUrlPlaceholder: 'https://your-llm-server.com or http://localhost:11434',
    apiKeyPlaceholder: 'API key (if required)',
  },
};

/**
 * Authentication type options for custom providers.
 */
export const AUTH_TYPE_OPTIONS = [
  { value: 'none', label: 'No Authentication' },
  { value: 'bearer', label: 'Bearer Token' },
  { value: 'api_key_header', label: 'API Key Header' },
  { value: 'basic', label: 'Basic Auth' },
];

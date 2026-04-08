export interface ModelRoutingConfig {
  id: string;
  provider_id: string;
  model_id: string;
  task_types: string[];
  prompt_sizes: string[];
  cost_tier: string;
  latency_tier: string;
  quality_tier: string;
  is_enabled: boolean;
  is_fallback: boolean;
  created_at: string;
  updated_at: string;
}

export interface ModelRoutingConfigListResponse {
  configs: ModelRoutingConfig[];
  total: number;
}

export interface RoutingOption {
  value: string;
  label: string;
}

export interface RoutingMetadataResponse {
  tier_options: RoutingOption[];
  latency_options: RoutingOption[];
  prompt_size_options: RoutingOption[];
}

export interface BulkUpsertItem {
  id?: string | null;
  provider_id: string;
  model_id: string;
  task_types: string[];
  prompt_sizes: string[];
  cost_tier: string;
  latency_tier: string;
  quality_tier: string;
  is_enabled: boolean;
  is_fallback: boolean;
}
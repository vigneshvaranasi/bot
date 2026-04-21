export type AuthField = {
  key: string;
  label: string;
  type: "text" | "password" | "url";
  required?: boolean;
};

export type AuthSchema = Record<string, AuthField[]>;

export type IntegrationSyncStatus = "success" | "error" | "never";

export type Integration = {
  id: string;
  service_name: string;
  auth_type: keyof typeof AUTH_SCHEMAS;
  config: Record<string, string>;
  configured_secrets?: string[];
  is_active: boolean;
  last_synced_at?: string | null;
  last_sync_status?: string | null;
  last_sync_error?: string | null;
  updated_at?: string;
};

export const CONNECTOR_TYPES = [
  { value: "servicenow", label: "ServiceNow" },
] as const;

export type ConnectorType = (typeof CONNECTOR_TYPES)[number]["value"];

export const AUTH_SCHEMAS: AuthSchema = {
  basic_auth: [
    { key: "url", label: "Instance URL", type: "url", required: true },
    { key: "username", label: "Username", type: "text", required: true },
    { key: "password", label: "Password", type: "password", required: true },
  ],

  api_token: [
    { key: "url", label: "Instance URL", type: "url", required: true },
    { key: "email", label: "Email", type: "text", required: true },
    { key: "api_token", label: "API Token", type: "password", required: true },
  ],

  oauth2: [
    { key: "url", label: "Instance URL", type: "url", required: true },
    { key: "client_id", label: "Client ID", type: "text", required: true },
    { key: "client_secret", label: "Client Secret", type: "password", required: true },
    { key: "token_url", label: "Token URL", type: "url", required: true },
  ],
};
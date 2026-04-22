export type AuthField = {
  key: string;
  label: string;
  type: "text" | "password" | "url" | "textarea";
  required?: boolean;
  placeholder?: string;
  help?: string;
};

export type ConnectorType = "servicenow" | "jira";

export type AuthType =
  | "basic_auth"
  | "api_token"
  | "oauth2"
  | "pat";

export type Integration = {
  id: string;
  service_name: string;
  connector_type: ConnectorType;
  auth_type: AuthType;
  config: Record<string, string>;
  configured_secrets?: string[];
  is_active: boolean;
  last_synced_at?: string | null;
  last_sync_status?: string | null;
  last_sync_error?: string | null;
  updated_at?: string;
};

export const CONNECTOR_TYPES: { value: ConnectorType; label: string }[] = [
  { value: "servicenow", label: "ServiceNow" },
  { value: "jira", label: "Jira" },
];

export const AUTH_TYPE_LABELS: Record<AuthType, string> = {
  basic_auth: "Basic Auth",
  api_token: "API Token",
  oauth2: "OAuth 2.0",
  pat: "Personal Access Token",
};

const urlField: AuthField = {
  key: "url",
  label: "Instance URL",
  type: "url",
  required: true,
};

const jiraProjectField: AuthField = {
  key: "project_key",
  label: "Project / Space Key",
  type: "text",
  placeholder: "e.g. SUP",
  help: "Provide either a project key or a JQL query below.",
};

const jiraJqlField: AuthField = {
  key: "jql",
  label: "Custom JQL (optional)",
  type: "textarea",
  placeholder: 'issuetype = "Incident" AND labels = "production"',
  help: "AND-combined with the project filter above, if both are set.",
};

export const CONNECTOR_AUTH_SCHEMAS: Record<
  ConnectorType,
  Partial<Record<AuthType, AuthField[]>>
> = {
  servicenow: {
    basic_auth: [
      urlField,
      { key: "username", label: "Username", type: "text", required: true },
      { key: "password", label: "Password", type: "password", required: true },
    ],
    api_token: [
      urlField,
      { key: "email", label: "Email", type: "text", required: true },
      { key: "api_token", label: "API Token", type: "password", required: true },
    ],
    oauth2: [
      urlField,
      { key: "client_id", label: "Client ID", type: "text", required: true },
      { key: "client_secret", label: "Client Secret", type: "password", required: true },
      { key: "token_url", label: "Token URL", type: "url", required: true },
    ],
  },

  jira: {
    api_token: [
      urlField,
      { key: "email", label: "Email", type: "text", required: true },
      { key: "api_token", label: "API Token", type: "password", required: true },
      jiraProjectField,
      jiraJqlField,
    ],
    basic_auth: [
      urlField,
      { key: "username", label: "Username", type: "text", required: true },
      { key: "password", label: "Password", type: "password", required: true },
      jiraProjectField,
      jiraJqlField,
    ],
    pat: [
      urlField,
      { key: "access_token", label: "Personal Access Token", type: "password", required: true },
      jiraProjectField,
      jiraJqlField,
    ],
  },
};

export type IntegrationSyncStatus = "success" | "error" | "never";

export const getAuthTypesForConnector = (
  connector: ConnectorType
): AuthType[] => Object.keys(CONNECTOR_AUTH_SCHEMAS[connector]) as AuthType[];

export const getAuthFields = (
  connector: ConnectorType,
  authType: AuthType
): AuthField[] => CONNECTOR_AUTH_SCHEMAS[connector]?.[authType] ?? [];
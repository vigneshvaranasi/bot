/**
 * RBAC Permission Types
 *
 * Implements a 3-level permission hierarchy:
 * Permissions (atomic) -> Permission Sets (groups) -> Roles -> Users
 */

// ==================== Permission Types ====================

export interface Permission {
  id: string;
  code: string;
  name: string;
  description?: string;
  category: string;
  is_system: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface PermissionListResponse {
  status: string;
  permissions: Permission[];
}

export interface PermissionCategoryResponse {
  status: string;
  categories: string[];
}

// ==================== Permission Set Types ====================

export interface PermissionSet {
  id: string;
  code: string;
  name: string;
  description?: string;
  created_at?: string;
  updated_at?: string;
  permissions: Permission[];
}

export interface PermissionSetBrief {
  id: string;
  code: string;
  name: string;
  description?: string;
}

export interface PermissionSetCreate {
  code: string;
  name: string;
  description?: string;
  permission_codes: string[];
}

export interface PermissionSetUpdate {
  name?: string;
  description?: string;
  permission_codes?: string[];
}

export interface PermissionSetListResponse {
  status: string;
  permission_sets: PermissionSet[];
}

// ==================== Role Types ====================

export interface Role {
  id: string;
  name: string;
  description?: string;
  created_at?: string;
  updated_at?: string;
  permission_sets: PermissionSetBrief[];
}

export interface RoleBrief {
  id: string;
  name: string;
  description?: string;
}

export interface RoleCreate {
  name: string;
  description?: string;
  permission_set_codes: string[];
}

export interface RoleUpdate {
  name?: string;
  description?: string;
  permission_set_codes?: string[];
}

export interface RoleListResponse {
  status: string;
  roles: Role[];
}

export interface RoleEffectivePermissionsResponse {
  status: string;
  role_id: string;
  role_name: string;
  permissions: string[];
}

// ==================== User Role Types ====================

export interface UserRole {
  role_id: string;
  role_name: string;
  assigned_at?: string;
  assigned_by?: string;
}

export interface UserRolesResponse {
  status: string;
  user_id: string;
  roles: UserRole[];
}

export interface UserEffectivePermissionsResponse {
  status: string;
  user_id: string;
  permissions: string[];
}

// ==================== Direct User Permission Types ====================

export interface UserDirectPermission {
  permission_id: string;
  permission_code: string;
  permission_name: string;
  assigned_at?: string;
  assigned_by?: string;
}

export interface UserDirectPermissionsResponse {
  status: string;
  user_id: string;
  direct_permissions: UserDirectPermission[];
}

export interface UserDirectPermissionSet {
  permission_set_id: string;
  permission_set_code: string;
  permission_set_name: string;
  assigned_at?: string;
  assigned_by?: string;
}

export interface UserDirectPermissionSetsResponse {
  status: string;
  user_id: string;
  direct_permission_sets: UserDirectPermissionSet[];
}

export interface UserEffectivePermissionsDetailedResponse {
  status: string;
  user_id: string;
  from_roles: string[];
  from_direct_sets: string[];
  from_direct_permissions: string[];
  effective: string[];
}

// ==================== Permission Categories ====================

export const PERMISSION_CATEGORIES = {
  aiml: "AI/ML Settings",
  auth: "Authentication",
  llm_provider: "LLM Providers",
  integration: "Integrations",
  user: "User Management",
  role: "Role Management",
  permission_set: "Permission Sets",
  feedback: "Feedback & Golden Examples",
  knowledge_base: "Knowledge Base",
  history: "History/Audit",
  chat: "Chat",
  system: "System",
} as const;

export type PermissionCategory = keyof typeof PERMISSION_CATEGORIES;

// ==================== Common Permission Codes ====================

export const PERMISSIONS = {
  // AI/ML
  AIML_VIEW: "aiml.view",
  AIML_EDIT: "aiml.edit",

  // Auth
  AUTH_VIEW: "auth.view",
  AUTH_EDIT: "auth.edit",

  // LLM Providers
  LLM_PROVIDER_VIEW: "llm_provider.view",
  LLM_PROVIDER_CREATE: "llm_provider.create",
  LLM_PROVIDER_EDIT: "llm_provider.edit",
  LLM_PROVIDER_DELETE: "llm_provider.delete",
  LLM_PROVIDER_TEST: "llm_provider.test",

  // Integrations
  INTEGRATION_VIEW: "integration.view",
  INTEGRATION_CREATE: "integration.create",
  INTEGRATION_EDIT: "integration.edit",
  INTEGRATION_DELETE: "integration.delete",
  INTEGRATION_SYNC: "integration.sync",

  // Users
  USER_VIEW: "user.view",
  USER_EDIT: "user.edit",
  USER_DELETE: "user.delete",

  // Roles
  ROLE_VIEW: "role.view",
  ROLE_CREATE: "role.create",
  ROLE_EDIT: "role.edit",
  ROLE_DELETE: "role.delete",

  // Permission Sets
  PERMISSION_SET_VIEW: "permission_set.view",
  PERMISSION_SET_CREATE: "permission_set.create",
  PERMISSION_SET_EDIT: "permission_set.edit",
  PERMISSION_SET_DELETE: "permission_set.delete",

  // Feedback & Golden Examples
  FEEDBACK_VIEW: "feedback.view",
  FEEDBACK_MANAGE: "feedback.manage",
  GOLDEN_EXAMPLE_VIEW: "golden_example.view",
  GOLDEN_EXAMPLE_CREATE: "golden_example.create",
  GOLDEN_EXAMPLE_EDIT: "golden_example.edit",
  GOLDEN_EXAMPLE_DELETE: "golden_example.delete",

  // Knowledge Base
  KB_VIEW: "kb.view",
  KB_UPLOAD: "kb.upload",
  KB_VALIDATE: "kb.validate",
  KB_INGEST: "kb.ingest",
  KB_VERSION_MANAGE: "kb.version_manage",
  KB_ROLLBACK: "kb.rollback",

  // History
  HISTORY_VIEW: "history.view",
  HISTORY_ROLLBACK: "history.rollback",

  // Chat
  CHAT_USE: "chat.use",

  // System
  SYSTEM_VIEW: "system.view",
  SYSTEM_EDIT: "system.edit",
} as const;

export type PermissionCode = (typeof PERMISSIONS)[keyof typeof PERMISSIONS];

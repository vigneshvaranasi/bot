import http from "../utils/http";
import type {
  Permission,
  PermissionListResponse,
  PermissionCategoryResponse,
  PermissionSet,
  PermissionSetCreate,
  PermissionSetUpdate,
  PermissionSetListResponse,
  Role,
  RoleCreate,
  RoleUpdate,
  RoleListResponse,
  RoleEffectivePermissionsResponse,
  UserEffectivePermissionsResponse,
} from "../types/Permission";

// ==================== Permission API ====================

/**
 * Fetch all permissions.
 */
export const fetchPermissions = async (): Promise<Permission[]> => {
  const response = await http.get<PermissionListResponse>("/permissions");
  return response.data.permissions;
};

/**
 * Fetch all permission categories.
 */
export const fetchPermissionCategories = async (): Promise<string[]> => {
  const response = await http.get<PermissionCategoryResponse>("/permissions/categories");
  return response.data.categories;
};

/**
 * Fetch current user's effective permissions.
 */
export const fetchMyPermissions = async (): Promise<string[]> => {
  const response = await http.get<UserEffectivePermissionsResponse>("/permissions/me");
  return response.data.permissions;
};

// ==================== Permission Set API ====================

/**
 * Fetch all permission sets.
 */
export const fetchPermissionSets = async (): Promise<PermissionSet[]> => {
  const response = await http.get<PermissionSetListResponse>("/permissions/sets");
  return response.data.permission_sets;
};

/**
 * Fetch a permission set by ID.
 */
export const fetchPermissionSet = async (id: string): Promise<PermissionSet> => {
  const response = await http.get<PermissionSet>(`/permissions/sets/${id}`);
  return response.data;
};

/**
 * Create a new permission set.
 */
export const createPermissionSet = async (data: PermissionSetCreate): Promise<PermissionSet> => {
  const response = await http.post<PermissionSet>("/permissions/sets", data);
  return response.data;
};

/**
 * Update a permission set.
 */
export const updatePermissionSet = async (
  id: string,
  data: PermissionSetUpdate
): Promise<PermissionSet> => {
  const response = await http.put<PermissionSet>(`/permissions/sets/${id}`, data);
  return response.data;
};

/**
 * Delete a permission set.
 */
export const deletePermissionSet = async (id: string): Promise<void> => {
  await http.delete(`/permissions/sets/${id}`);
};

// ==================== Role API ====================

/**
 * Fetch all roles.
 */
export const fetchRoles = async (): Promise<Role[]> => {
  const response = await http.get<RoleListResponse>("/permissions/roles");
  return response.data.roles;
};

/**
 * Fetch a role by ID.
 */
export const fetchRole = async (id: string): Promise<Role> => {
  const response = await http.get<Role>(`/permissions/roles/${id}`);
  return response.data;
};

/**
 * Create a new role.
 */
export const createRole = async (data: RoleCreate): Promise<Role> => {
  const response = await http.post<Role>("/permissions/roles", data);
  return response.data;
};

/**
 * Update a role.
 */
export const updateRole = async (id: string, data: RoleUpdate): Promise<Role> => {
  const response = await http.put<Role>(`/permissions/roles/${id}`, data);
  return response.data;
};

/**
 * Delete a role.
 */
export const deleteRole = async (id: string): Promise<void> => {
  await http.delete(`/permissions/roles/${id}`);
};

/**
 * Fetch effective permissions for a role.
 */
export const fetchRolePermissions = async (id: string): Promise<string[]> => {
  const response = await http.get<RoleEffectivePermissionsResponse>(
    `/permissions/roles/${id}/permissions`
  );
  return response.data.permissions;
};

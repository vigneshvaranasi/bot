import http from "../utils/http";
import type {
  Permission,
  PermissionListResponse,
  PermissionSet,
  PermissionSetCreate,
  PermissionSetUpdate,
  PermissionSetListResponse,
  Role,
  RoleCreate,
  RoleUpdate,
  RoleListResponse,
  UserEffectivePermissionsResponse,
  UserDirectPermissionsResponse,
  UserDirectPermissionSetsResponse,
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

// ==================== Direct User Permission API ====================

/**
 * Fetch direct permissions assigned to a user (bypassing roles).
 */
export const fetchUserDirectPermissions = async (
  userId: string
): Promise<UserDirectPermissionsResponse> => {
  const response = await http.get<UserDirectPermissionsResponse>(
    `/admin/users/${userId}/permissions/direct`
  );
  return response.data;
};

/**
 * Update all direct permissions for a user (replaces existing).
 */
export const updateUserDirectPermissions = async (
  userId: string,
  permissionIds: string[]
): Promise<UserDirectPermissionsResponse> => {
  const response = await http.put<UserDirectPermissionsResponse>(
    `/admin/users/${userId}/permissions/direct`,
    { permission_ids: permissionIds }
  );
  return response.data;
};

// ==================== Direct User Permission Set API ====================

/**
 * Fetch direct permission sets assigned to a user (bypassing roles).
 */
export const fetchUserDirectPermissionSets = async (
  userId: string
): Promise<UserDirectPermissionSetsResponse> => {
  const response = await http.get<UserDirectPermissionSetsResponse>(
    `/admin/users/${userId}/permission-sets/direct`
  );
  return response.data;
};

/**
 * Update all direct permission sets for a user (replaces existing).
 */
export const updateUserDirectPermissionSets = async (
  userId: string,
  permissionSetIds: string[]
): Promise<UserDirectPermissionSetsResponse> => {
  const response = await http.put<UserDirectPermissionSetsResponse>(
    `/admin/users/${userId}/permission-sets/direct`,
    { permission_set_ids: permissionSetIds }
  );
  return response.data;
};

import http from "../utils/http";

export interface UserRole {
    role_id: string;
    role_name: string;
    assigned_at?: string;
}

export interface AdminUser {
    id: string;
    email: string;
    is_active: boolean;
    role_id?: string;  // Legacy field
    role_name?: string;  // Legacy field
    roles: UserRole[];  // New multi-role field
}

export interface Role {
    id: string;
    name: string;
    description?: string;
}

export interface PaginatedUsersResponse {
    users: AdminUser[];
    total: number;
    limit: number;
    offset: number;
    has_more: boolean;
}

/**
 * Fetch paginated users with optional search.
 */
export const fetchUsers = async (
    limit: number = 20,
    offset: number = 0,
    search?: string
): Promise<PaginatedUsersResponse> => {
    let url = `/admin/users?limit=${limit}&offset=${offset}`;
    if (search) {
        url += `&search=${encodeURIComponent(search)}`;
    }
    const response = await http.get(url);
    return response.data;
};

/**
 * Update user (legacy single role).
 */
export const updateUser = async (userId: string, data: { is_active: boolean; role_id: string }) => {
    const response = await http.put(`/admin/users/${userId}`, data);
    return response.data;
};

/**
 * Delete a user.
 */
export const deleteUser = async (userId: string) => {
    const response = await http.delete(`/admin/users/${userId}`);
    return response.data;
};

/**
 * Fetch all roles.
 */
export const fetchRoles = async (): Promise<Role[]> => {
    const response = await http.get("/roles/");
    return response.data;
};

// ==================== Multi-role API ====================

/**
 * Get all roles assigned to a user.
 */
export const fetchUserRoles = async (userId: string): Promise<UserRole[]> => {
    const response = await http.get(`/admin/users/${userId}/roles`);
    return response.data.roles;
};

/**
 * Replace all roles for a user.
 */
export const updateUserRoles = async (userId: string, roleIds: string[]): Promise<void> => {
    await http.put(`/admin/users/${userId}/roles`, { role_ids: roleIds });
};

/**
 * Assign a single role to a user.
 */
export const assignUserRole = async (userId: string, roleId: string): Promise<void> => {
    await http.post(`/admin/users/${userId}/roles`, { role_id: roleId });
};

/**
 * Remove a role from a user.
 */
export const removeUserRole = async (userId: string, roleId: string): Promise<void> => {
    await http.delete(`/admin/users/${userId}/roles/${roleId}`);
};

// ==================== Role Management API ====================

export interface RoleDetail extends Role {
    permission_sets: Array<{
        id: string;
        code: string;
        name: string;
    }>;
}

export interface CreateRoleData {
    name: string;
    description?: string;
    permission_set_ids?: string[];
}

export interface UpdateRoleData {
    name?: string;
    description?: string;
    permission_set_ids?: string[];
}

/**
 * Get a role with its permission sets.
 */
export const fetchRoleDetail = async (roleId: string): Promise<RoleDetail> => {
    const response = await http.get(`/roles/${roleId}`);
    return response.data;
};

/**
 * Create a new role.
 */
export const createRole = async (data: CreateRoleData): Promise<Role> => {
    const response = await http.post("/roles/", data);
    return response.data;
};

/**
 * Update an existing role.
 */
export const updateRole = async (roleId: string, data: UpdateRoleData): Promise<Role> => {
    const response = await http.put(`/roles/${roleId}`, data);
    return response.data;
};

/**
 * Delete a role (soft delete).
 */
export const deleteRole = async (roleId: string): Promise<void> => {
    await http.delete(`/roles/${roleId}`);
};

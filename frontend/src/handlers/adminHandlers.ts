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
 * Delete a user.
 */
export const deleteUser = async (userId: string) => {
    const response = await http.delete(`/admin/users/${userId}`);
    return response.data;
};

// ==================== Multi-role API ====================

/**
 * Replace all roles for a user.
 */
export const updateUserRoles = async (userId: string, roleIds: string[]): Promise<void> => {
    await http.put(`/admin/users/${userId}/roles`, { role_ids: roleIds });
};

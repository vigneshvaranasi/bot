import http from "../utils/http";

export interface AdminUser {
    id: string;
    email: string;
    is_active: boolean;
    role_id: string;
    role_name: string;
}

export interface Role {
    id: string;
    name: string;
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

export const updateUser = async (userId: string, data: { is_active: boolean; role_id: string }) => {
    const response = await http.put(`/admin/users/${userId}`, data);
    return response.data;
};

export const deleteUser = async (userId: string) => {
    const response = await http.delete(`/admin/users/${userId}`);
    return response.data;
};

export const fetchRoles = async (): Promise<Role[]> => {
    const response = await http.get("/roles/");
    return response.data;
};

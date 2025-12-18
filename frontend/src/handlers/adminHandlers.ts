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

export const fetchUsers = async (): Promise<AdminUser[]> => {
    const response = await http.get("/admin/users");
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

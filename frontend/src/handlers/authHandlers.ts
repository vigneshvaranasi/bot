import { BE_URL } from "../config/config";
import http from "../utils/http";
import { logger } from "../utils/logger";

// handler for user signup (pre-auth, no token needed)
export const signUpHandler = async (email: string, password: string, role_id: string) => {
    try {
        const { data } = await http.post("/auth/signup", { email, password, role_id });
        return data;
    } catch (error) {
        logger.error("Error signing up:", error);
        throw error;
    }
};

// handler for user login (pre-auth, no token needed)
export const loginHandler = async (email: string, password: string) => {
    try {
        const { data } = await http.post("/auth/login", { email, password });
        return data;
    } catch (error) {
        logger.error("Error logging in:", error);
        throw error;
    }
};

// handler for verify - requires explicit token parameter (not from localStorage)
export const verifyTokenHandler = async (token: string) => {
  try {
    const response = await fetch(`${BE_URL}/auth/verify`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      }
    });

    if (!response.ok) {
      throw new Error('Token verification failed');
    }

    const data = await response.json();
    return data;
  } catch (error) {
    logger.error('Verify token error:', error);
    return { success: false };
  }
};

// handler to get all roles (public endpoint)
export const getAllRolesHandler = async () => {
    try {
        const { data } = await http.get("/roles/");
        return data;
    } catch (error) {
        logger.error("Error fetching roles:", error);
        throw error;
    }
};

export const updatePasswordHandler = async (password: string) => {
    try {
        const response = await http.post("/auth/password", { password });
        return response.data;
    } catch (error) {
        logger.error("Error updating password:", error);
        throw error;
    }
};
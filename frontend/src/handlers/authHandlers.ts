import { BE_URL } from "../config/config";


// handler for user signup
export const signUpHandler = async (email: string, password:string, role_id:string)=>{
    try {
        const response = await fetch(`${BE_URL}/auth/signup`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ email, password, role_id })
        });
        if (!response.ok) {
            throw new Error("Failed to sign up");
        }
        const data = await response.json();
        return data;
    } catch (error) {
        console.error("Error signing up:", error);
        throw error;
    }
}

// handler for user login
export const loginHandler = async (email: string, password: string) => {
    try {
        const response = await fetch(`${BE_URL}/auth/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ email, password })
        });
        if (!response.ok) {
            throw new Error("Failed to log in");
        }
        const data = await response.json();
        return data;
    } catch (error) {
        console.error("Error logging in:", error);
        throw error;
    }
}
// handler for verify
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
    console.error('Verify token error:', error);
    return { success: false };
  }
};

// handler to get all roles
export const getAllRolesHandler = async()=>{
    try {
        const response = await fetch(`${BE_URL}/roles/`, {
            method: "GET",
            headers: {
                "Content-Type": "application/json"
            }
        });
        if (!response.ok) {
            throw new Error("Failed to fetch roles");
        }
        const data = await response.json();
        return data;
    } catch (error) {
        console.error("Error fetching roles:", error);
        throw error;
    }
}
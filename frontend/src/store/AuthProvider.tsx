import { createContext, useEffect, useState } from "react";
import { verifyTokenHandler } from "../handlers/authHandlers";


type UserData = {
  email: string;
  token: string;
  role_id: string;
};

interface AuthContextType {
  user: UserData | null;
  loading: boolean;
  login: (userData: Omit<UserData, 'token'>, token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: false,
  login: () => {},
  logout: () => {},
});

const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [user, setUser] = useState<UserData | null>(() => {
    const storedUser = localStorage.getItem("user");
    return storedUser ? JSON.parse(storedUser) : null;
  });
  const [loading, setLoading] = useState<boolean>(true);

  // Centralized login method
  const login = (userData: Omit<UserData, 'token'>, token: string) => {
    const newUser = { ...userData, token };
    setUser(newUser);
    localStorage.setItem("user", JSON.stringify(newUser));
    localStorage.setItem("token", token);
  };

  // Centralized logout method
  const logout = () => {
    setUser(null);
    localStorage.removeItem("user");
    localStorage.removeItem("token");
  };

  async function verifyToken() {
    const token = localStorage.getItem("token");
    if (!token) {
      logout();
      setLoading(false);
      return;
    }
    try {
      const userData = await verifyTokenHandler(token);
      if (userData.success) {
        login({ email: userData.email, role_id: userData.role_id }, token);
      } else {
        logout();
      }
    } catch (error) {
      console.error("Token verification failed:", error);
      logout();
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    verifyToken();
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export default AuthProvider;
export { AuthContext };

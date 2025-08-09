import { createContext, useEffect, useState } from "react";
import { verifyTokenHandler } from "../handlers/authHandlers";

type UserData = {
  email: string;
  token: string;
  role_id: string;
};

const AuthContext = createContext<{
  user: UserData | null;
  setUser: React.Dispatch<React.SetStateAction<UserData | null>>;
  loading: boolean;
  setLoading: React.Dispatch<React.SetStateAction<boolean>>;
  isLoggedIn: boolean;
  setIsLoggedIn: React.Dispatch<React.SetStateAction<boolean>>;
}>({
  user: null,
  setUser: () => {},
  loading: false,
  setLoading: () => {},
  isLoggedIn: false,
  setIsLoggedIn: () => {},
});

const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [user, setUser] = useState<UserData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [isLoggedIn, setIsLoggedIn] = useState<boolean>(false);

  async function verifyToken() {
    const token = localStorage.getItem("token");

    if (!token) {
      setIsLoggedIn(false);
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const userData = await verifyTokenHandler(token);
      if (userData.success) {
        setUser({
          email: userData.email,
          token: token,
          role_id: userData.role_id,
        });
        setIsLoggedIn(true);
      } else {
        setIsLoggedIn(false);
        setUser(null);
      }
    } catch (error) {
      console.error("Token verification failed:", error);
      setIsLoggedIn(false);
      setUser(null);
      localStorage.removeItem("token");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    verifyToken();
  }, []);

  return (
    <AuthContext.Provider
      value={{ user, setUser, loading, setLoading, isLoggedIn, setIsLoggedIn }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export default AuthProvider;
export { AuthContext };

import { useState, useEffect } from "react";
import InputBox from "../components/ui/InputBox";
import { Button } from "../components/ui/Button";
import { useAuthContext } from "../hooks/useAuthContext";
import http from "../utils/http";
import { useNavigate } from "react-router-dom";
import Spinner from "../components/ui/Spinner";

function Login() {
  const [userData, setUserData] = useState<{
    email: string;
    password: string;
  }>({
    email: "",
    password: "",
  });
  const [providers, setProviders] = useState<string[]>([]);
  const navigate = useNavigate();
  const { login, loading } = useAuthContext();

  useEffect(() => {
    const fetchProviders = async () => {
      try {
        const response = await http.get("/auth/providers");
        setProviders(response.data.providers);
      } catch (error) {
        console.error("Failed to fetch providers", error);
      }
    };
    fetchProviders();
  }, []);

  const handleLogin = async () => {
    const { email, password } = userData;
    try {
      const response = await http.post("/auth/login", { email, password });
      if (response.data.access_token) {
        await login(response.data.access_token);
        navigate("/");
      }
    } catch (error) {
      console.error("Login failed:", error);
      alert("Login failed");
    }
  };

  const handleOAuthLogin = async (provider: string) => {
    try {
      const response = await http.get(`/auth/oauth/${provider}`);
      window.location.href = response.data.authorization_url;
    } catch (error) {
      console.error("OAuth init failed", error);
    }
  };

  const isLocalEnabled = providers.includes("local");

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Spinner size={48} />
      </div>
    );
  }

  return (
    <div
      className="flex flex-col items-center justify-center min-h-screen bg-gray-100"
      style={{ fontFamily: "Inter, sans-serif" }}
    >
      <h1 className="text-3xl font-bold mb-6">Login</h1>
      <div className="bg-white p-8 rounded shadow-md w-full max-w-sm flex flex-col gap-4">
        {isLocalEnabled && (
          <>
            <InputBox
              type="email"
              variant="primary"
              placeholder="Enter your email"
              value={userData.email}
              onChange={(value) => setUserData({ ...userData, email: value })}
            />
            <InputBox
              variant="primary"
              type="password"
              placeholder="Enter your password"
              value={userData.password}
              onChange={(value) => setUserData({ ...userData, password: value })}
            />
            <Button
              variant="secondary"
              className="mt-4"
              onClick={handleLogin}
              children="Log In"
            />
          </>
        )}
        
        {providers.filter(p => p !== 'local').map(provider => (
          <Button
            key={provider}
            variant="primary"
            className="mt-2 capitalize"
            onClick={() => handleOAuthLogin(provider)}
          >
            Login with {provider}
          </Button>
        ))}
      </div>
    </div>
  );
}

export default Login;

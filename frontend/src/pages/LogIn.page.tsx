import { useState } from "react";
import InputBox from "../components/ui/InputBox";
import { Button } from "../components/ui/Button";
import { useAuthContext } from "../hooks/useAuthContext";
import { loginHandler } from "../handlers/authHandlers";
import { useNavigate } from "react-router-dom";
function Login() {
  const [userData, setUserData] = useState<{
    email: string;
    password: string;
  }>({
    email: "",
    password: "",
  });
  const navigate = useNavigate();
  const { login, loading } = useAuthContext();
  const handleLogin = async () => {
    const { email, password } = userData;
    const loginData = await loginHandler(email, password);
    if (loginData.success) {
      login({
        email: loginData.email,
        role_id: loginData.role_id,
      }, loginData.jwt);
      navigate("/");
    } else {
      console.error("Login failed:", loginData.message);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        Loading...
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
      </div>
    </div>
  );
}

export default Login;

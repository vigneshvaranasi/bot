import { useEffect, useState } from "react";
import InputBox from "../components/ui/InputBox";
import Dropdown from "../components/ui/Dropdown";
import { getAllRolesHandler, signUpHandler, loginHandler } from "../handlers/authHandlers";
import { Button } from "../components/ui/Button";
import type { RolesDropDown } from "../types/Roles";
import { useAuthContext } from "../hooks/useAuthContext";
import { useNavigate } from "react-router-dom";
import http from "../utils/http";

function Signup() {
  const [userData, setUserData] = useState<{
    email: string;
    password: string;
    role_id: string;
  }>({
    email: "",
    password: "",
    role_id: "",
  });

  const navigate = useNavigate();

  const [allRoles, setAllRoles] = useState<RolesDropDown>([]);
  const [providers, setProviders] = useState<string[]>([]);

  const { login, loading } = useAuthContext();

  useEffect(() => {
    const fetchRoles = async () => {
      try {
        const roles = await getAllRolesHandler();
        const formattedRoles = roles.map((role: any) => ({
          label: role.name,
          value: role.id,
        }));
        setAllRoles(formattedRoles);
        console.log("Fetched roles:", formattedRoles);
      } catch (error) {
        console.error("Error fetching roles:", error);
      }
    };
    fetchRoles();

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

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        Loading...
      </div>
    );
  }

  const handleSignup = async () => {
    const { email, password, role_id } = userData;
    try {
      await signUpHandler(email, password, role_id);
      const loginData = await loginHandler(email, password);
      await login(loginData.access_token);
      navigate("/");
    } catch (error) {
      console.error("Signup failed:", error);
      alert("Signup failed. Please try again.");
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

  return (
    <div
      className="flex flex-col items-center justify-center min-h-screen bg-gray-100"
      style={{ fontFamily: "Inter, sans-serif" }}
    >
      <h1 className="text-3xl font-bold mb-6">Sign Up</h1>
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
            <Dropdown
              options={[
                { label: "Select Role", value: "" },
                ...allRoles.map((role) => ({
                  label: role.label,
                  value: role.value,
                })),
              ]}
              placeholder="Select your role"
              value={userData.role_id}
              onChange={(value) => setUserData({ ...userData, role_id: value })}
            />
            <Button
              variant="secondary"
              className="mt-4"
              onClick={handleSignup}
              children="Sign Up"
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
            Sign up with {provider}
          </Button>
        ))}
      </div>
    </div>
  );
}

export default Signup;

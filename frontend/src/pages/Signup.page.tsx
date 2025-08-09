import { useEffect, useState } from "react";
import InputBox from "../components/ui/InputBox";
import Dropdown from "../components/ui/Dropdown";
import { getAllRolesHandler, signUpHandler } from "../handlers/authHandlers";
import { Button } from "../components/ui/Button";
import type { RolesDropDown } from "../types/Roles";
import { useAuthContext } from "../hooks/useAuthContext";
import { useNavigate } from "react-router-dom";
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

  const { setUser, setLoading, setIsLoggedIn, loading } = useAuthContext();

  useEffect(() => {
    setLoading(true);
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
      setLoading(false);
    };
    fetchRoles();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        Loading...
      </div>
    );
  }

  const handleSignup = async () => {
    console.log("User Data:", userData);
    setLoading(true);
    const { email, password, role_id } = userData;
    const signUpData = await signUpHandler(email, password, role_id);
    if(signUpData.success){
      setLoading(false);
       setUser({ 
        email: signUpData.email,
        role_id: signUpData.role_id,
        token: signUpData.jwt
      });
      setIsLoggedIn(true);
      localStorage.setItem("token", signUpData.jwt);
      navigate("/");
    }
    else {
      setLoading(false);
      console.error("Signup failed:", signUpData.message);
    }
    if (signUpData) {
      console.log("Sign Up Successful:", signUpData);
    }
  };

  return (
    <div
      className="flex flex-col items-center justify-center min-h-screen bg-gray-100"
      style={{ fontFamily: "Inter, sans-serif" }}
    >
      <h1 className="text-3xl font-bold mb-6">Sign Up</h1>
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
      </div>
    </div>
  );
}

export default Signup;

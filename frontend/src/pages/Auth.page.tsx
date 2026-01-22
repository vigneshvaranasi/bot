import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/ui/Button";
import InputBox from "../components/ui/InputBox";
import http from "../utils/http";
import { useAuthContext } from "../hooks/useAuthContext";
import { logger } from "../utils/logger";
import { toast } from "react-hot-toast";
import GoogleIcon from "../assets/icons/google.svg";
import MicrosoftIcon from "../assets/icons/microsoft.svg";
import GithubIcon from "../assets/icons/github.svg";

const AuthPage = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [providers, setProviders] = useState<string[]>([]);
  const [fetchingProviders, setFetchingProviders] = useState(true);
  const { login, user } = useAuthContext();
  const navigate = useNavigate();

  useEffect(() => {
    const fetchProviders = async () => {
      try {
        const response = await http.get("/auth/providers");
        if (response.data?.providers) {
          setProviders(response.data.providers);
        }
      } catch (error) {
        logger.error("Failed to fetch providers", error);
      } finally {
        setFetchingProviders(false);
      }
    };
    fetchProviders();
  }, []);

  useEffect(() => {
    if (user) {
      navigate("/");
    }
  }, [user, navigate]);

  const handleOAuthLogin = async (provider: string) => {
    try {
      const response = await http.get(`/auth/oauth/${provider}`);
      window.location.href = response.data.authorization_url;
    } catch (error) {
      logger.error("OAuth login failed", error);
      toast.error("Failed to initiate login");
    }
  };

  const getErrorMessage = (error: unknown): string => {
    if (error && typeof error === "object" && "response" in error) {
      const response = (error as { response?: { data?: { detail?: string | { msg?: string }[] } } }).response;
      const detail = response?.data?.detail;
      if (typeof detail === "string") {
        return detail;
      }
      // Handle Pydantic validation errors (array format)
      if (Array.isArray(detail) && detail.length > 0) {
        return detail.map(d => d.msg || String(d)).join(", ");
      }
    }
    return "Authentication failed. Please check your credentials.";
  };

  const handleEmailLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      // Try to login first
      try {
        const response = await http.post("/auth/login", { email, password });
        if (response.data?.access_token) {
          await login(response.data.access_token);
          return;
        }
      } catch (loginError) {
        // Login failed, try signup then login
        try {
          await http.post("/auth/signup", { email, password });
          const loginResponse = await http.post("/auth/login", { email, password });
          if (loginResponse.data?.access_token) {
            await login(loginResponse.data.access_token);
          }
        } catch (signupError) {
          // Show signup error (likely password validation)
          const errorMsg = getErrorMessage(signupError);
          logger.error("Signup failed", signupError);
          toast.error(errorMsg);
          return;
        }
      }
    } catch (error) {
      logger.error("Auth failed", error);
      toast.error(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-50">
      <div className="w-full max-w-md p-8 space-y-6 bg-white rounded-lg shadow-md">
        <h1 className="text-2xl font-semibold text-center text-gray-900">
          Log in or Sign up
        </h1>
        <div className="space-y-3">
          {!fetchingProviders && providers.length === 0 && (
            <div className="text-center text-gray-500 py-4">
              No authentication methods enabled.
            </div>
          )}
          {providers.includes("google") && (
            <Button
              onClick={() => handleOAuthLogin("google")}
              className="w-full flex justify-center items-center gap-3 bg-white text-gray-700 border border-gray-300 hover:bg-gray-50 transition-colors"
            >
              <img src={GoogleIcon} alt="Google" className="w-5 h-5" />
              <span>Continue with Google</span>
            </Button>
          )}
          {providers.includes("github") && (
            <Button
              onClick={() => handleOAuthLogin("github")}
              className="w-full flex justify-center items-center gap-3 bg-white text-gray-700 border border-gray-300 hover:bg-gray-50 transition-colors"
            >
              <img src={GithubIcon} alt="GitHub" className="w-5 h-5" />
              <span>Continue with GitHub</span>
            </Button>
          )}
          {providers.includes("microsoft") && (
            <Button
              onClick={() => handleOAuthLogin("microsoft")}
              className="w-full flex justify-center items-center gap-3 bg-white text-gray-700 border border-gray-300 hover:bg-gray-50 transition-colors"
            >
              <img src={MicrosoftIcon} alt="Microsoft" className="w-5 h-5" />
              <span>Continue with Microsoft</span>
            </Button>
          )}
        </div>

        {providers.includes("local") && providers.some(p => ["google", "github", "microsoft"].includes(p)) && (
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-300"></div>
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-2 bg-white text-gray-500">OR</span>
            </div>
          </div>
        )}

        {providers.includes("local") && (
          <form onSubmit={handleEmailLogin} className="space-y-4">
            <div>
              <InputBox
                value={email}
                onChange={setEmail}
                placeholder="Email address"
                type="email"
                variant="primary"
                className="w-full"
              />
            </div>
            <div>
              <InputBox
                value={password}
                onChange={setPassword}
                placeholder="Password"
                type="password"
                variant="primary"
                className="w-full"
              />
            </div>
            <Button
              type="submit"
              disabled={loading}
              className="w-full !bg-gray-900 hover:!bg-gray-800 !text-white font-medium py-3 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? "Loading..." : "Continue"}
            </Button>
          </form>
        )}
      </div>
    </div>
  );
};

export default AuthPage;

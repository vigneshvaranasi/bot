import { useEffect, useRef } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import http from "../utils/http";
import { useAuthContext } from "../hooks/useAuthContext";

const OAuthCallback = () => {
  const [searchParams] = useSearchParams();
  const { provider } = useParams();
  const navigate = useNavigate();
  const { login, refreshUser } = useAuthContext();
  const processedRef = useRef(false);

  useEffect(() => {
    const code = searchParams.get("code");
    const state = searchParams.get("state");

    if (code && state && provider) {
      if (processedRef.current) return;
      processedRef.current = true;

      const existingToken = localStorage.getItem("token");

      if (existingToken) {
        const params = new URLSearchParams({ code, state });
        http.get(`/auth/link/${provider}/callback?${params}`)
          .then(async () => {
            await refreshUser();
            navigate(`/settings/my-account?linked=${provider}`);
          })
          .catch((error) => {
            console.error("OAuth link callback failed", error);
            const detail = error?.response?.data?.detail || "Failed to link account";
            navigate(`/settings/my-account?link_error=${encodeURIComponent(detail)}`);
          });
      } else {
        const params = new URLSearchParams({ code, state });
        http.get(`/auth/oauth/${provider}/callback?${params}`)
          .then(async (response) => {
            if (response.data.access_token) {
              await login(response.data.access_token);
              navigate("/");
            }
          })
          .catch((error) => {
            console.error("OAuth callback failed", error);
            const detail = error?.response?.data?.detail || "Authentication failed";
            navigate(`/auth?error=${encodeURIComponent(detail)}`);
          });
      }
    } else {
      navigate("/auth");
    }
  }, [searchParams, provider, navigate, login, refreshUser]);

  return (
    <div className="flex items-center justify-center min-h-screen">
      <p className="text-3xl">Authenticating...</p>
    </div>
  );
};

export default OAuthCallback;

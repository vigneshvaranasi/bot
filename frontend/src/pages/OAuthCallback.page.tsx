import { useEffect, useRef } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import http from "../utils/http";
import { useAuthContext } from "../hooks/useAuthContext";

const OAuthCallback = () => {
  const [searchParams] = useSearchParams();
  const { provider } = useParams();
  const navigate = useNavigate();
  const { login } = useAuthContext();
  const processedRef = useRef(false);

  useEffect(() => {
    const code = searchParams.get("code");
    const state = searchParams.get("state");

    if (code && state && provider) {
      if (processedRef.current) return;
      processedRef.current = true;

      http.get(`/auth/oauth/${provider}/callback?code=${code}&state=${state}`)
        .then(async (response) => {
          if (response.data.access_token) {
            await login(response.data.access_token);
            navigate("/");
          }
        })
        .catch((error) => {
          console.error("OAuth callback failed", error);
          navigate("/auth");
        });
    } else {
        navigate("/auth");
    }
  }, [searchParams, provider, navigate, login]);

  return (
    <div className="flex items-center justify-center min-h-screen">
        <p className="text-3xl">
            Authenticating...
        </p>
    </div>
  );
};

export default OAuthCallback;

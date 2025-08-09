import { Navigate, Outlet } from "react-router-dom";
import { useAuthContext } from "../hooks/useAuthContext";

const ProtectedRoute = () => {
  const { isLoggedIn, loading } = useAuthContext();
  if (loading) {
    return (
      <div className="flex text-3xl justify-center items-center h-screen">
        Authenticating...
      </div>
    );
  }

  if (!loading && !isLoggedIn) {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
};

export default ProtectedRoute;
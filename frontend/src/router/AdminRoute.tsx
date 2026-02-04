import { Navigate, Outlet } from "react-router-dom";
import { useAuthContext } from "../hooks/useAuthContext";
import { usePermissions } from "../hooks/usePermissions";

const AdminRoute = () => {
  const { user, loading: authLoading } = useAuthContext();
  const { permissions, loading: permissionsLoading } = usePermissions();

  if (authLoading || permissionsLoading) {
    return (
      <div className="flex text-3xl justify-center items-center h-screen">
        Authenticating...
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }


  if (permissions.size === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-screen text-center px-6">
        <p className="text-lg font-semibold text-gray-900">Admin access required</p>
        <p className="text-sm text-gray-600 mt-2 max-w-md">
          You do not have permission to view this area. Please contact an administrator if you
          believe this is an error.
        </p>
      </div>
    );
  }

  return <Outlet />;
};

export default AdminRoute;

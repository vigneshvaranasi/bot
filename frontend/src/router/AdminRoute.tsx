import { Navigate, Outlet } from "react-router-dom";
import { useAuthContext } from "../hooks/useAuthContext";
import { usePermissions } from "../hooks/usePermissions";
import { PERMISSIONS } from "../types/Permission";

const ADMIN_PERMISSIONS = [
  PERMISSIONS.AIML_VIEW,
  PERMISSIONS.AIML_EDIT,
  PERMISSIONS.AUTH_VIEW,
  PERMISSIONS.AUTH_EDIT,
  PERMISSIONS.USER_VIEW,
  PERMISSIONS.USER_EDIT,
  PERMISSIONS.USER_DELETE,
  PERMISSIONS.ROLE_VIEW,
  PERMISSIONS.INTEGRATION_VIEW,
  PERMISSIONS.PERMISSION_SET_VIEW,
  PERMISSIONS.FEEDBACK_VIEW,
  PERMISSIONS.FEEDBACK_MANAGE,
  PERMISSIONS.KB_VIEW,
  PERMISSIONS.HISTORY_VIEW,
  PERMISSIONS.LLM_PROVIDER_VIEW,
];

const AdminRoute = () => {
  const { user, loading: authLoading } = useAuthContext();
  const { hasAnyPermission, loading: permissionsLoading } = usePermissions();

  if (authLoading || permissionsLoading) {
    return (
      <div className="flex text-3xl justify-center items-center h-screen">
        Authenticating...
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/auth" replace />;
  }

  if (!hasAnyPermission(...ADMIN_PERMISSIONS)) {
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

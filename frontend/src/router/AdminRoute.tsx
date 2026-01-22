import { Navigate, Outlet } from "react-router-dom";
import { useAuthContext } from "../hooks/useAuthContext";
import { usePermissions } from "../hooks/usePermissions";

/**
 * AdminRoute - Route guard for settings pages that require specific permissions.
 *
 * Unlike the old role-based approach (user.role === "admin"), this now uses the
 * RBAC permission system. Users need at least one view permission for any admin
 * area to access this route. Individual pages handle their own fine-grained
 * permission checks.
 */
const AdminRoute = () => {
  const { user, loading: authLoading } = useAuthContext();
  const { permissions, loading: permissionsLoading, hasAnyPermission } = usePermissions();

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

  // Check if user has any admin-level permissions
  // This is a broad check - individual pages handle specific permissions
  const adminPermissionPrefixes = [
    "aiml.", "auth.", "llm_provider.", "integration.",
    "user.", "role.", "permission_set.", "history.", "system."
  ];

  const hasAnyAdminPermission = permissions.size > 0 &&
    Array.from(permissions).some(p =>
      adminPermissionPrefixes.some(prefix => p.startsWith(prefix))
    );

  if (!hasAnyAdminPermission) {
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

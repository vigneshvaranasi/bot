import { useContext } from "react";
import { PermissionContext } from "../store/PermissionProvider";

/**
 * Hook for accessing and checking user permissions.
 *
 * @example
 * ```tsx
 * const { hasPermission, hasAnyPermission } = usePermissions();
 *
 * // Check single permission
 * if (hasPermission("aiml.edit")) {
 *   // User can edit AI/ML settings
 * }
 *
 * // Check any of multiple permissions
 * if (hasAnyPermission("aiml.view", "aiml.edit")) {
 *   // User can view or edit AI/ML settings
 * }
 *
 * // Conditional rendering
 * {hasPermission("user.delete") && (
 *   <Button onClick={handleDelete}>Delete User</Button>
 * )}
 * ```
 */
export function usePermissions() {
  const context = useContext(PermissionContext);

  if (!context) {
    throw new Error("usePermissions must be used within a PermissionProvider");
  }

  return context;
}

export default usePermissions;

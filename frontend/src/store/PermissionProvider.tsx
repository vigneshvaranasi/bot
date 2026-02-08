import { createContext, useCallback, useEffect, useState } from "react";
import { fetchMyPermissions } from "../handlers/permissionHandlers";
import { useAuthContext } from "../hooks/useAuthContext";
import { logger } from "../utils/logger";

interface PermissionContextType {
  permissions: Set<string>;
  loading: boolean;
  error: string | null;
  hasPermission: (code: string) => boolean;
  hasAnyPermission: (...codes: string[]) => boolean;
  hasAllPermissions: (...codes: string[]) => boolean;
  refreshPermissions: () => Promise<void>;
}

const PermissionContext = createContext<PermissionContextType>({
  permissions: new Set(),
  loading: true,
  error: null,
  hasPermission: () => false,
  hasAnyPermission: () => false,
  hasAllPermissions: () => false,
  refreshPermissions: async () => {},
});

const PermissionProvider = ({ children }: { children: React.ReactNode }) => {
  const { user } = useAuthContext();
  const [permissions, setPermissions] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const refreshPermissions = useCallback(async () => {
    if (!user) {
      setPermissions(new Set());
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const permissionList = await fetchMyPermissions();
      setPermissions(new Set(permissionList));
    } catch (err) {
      logger.error("Failed to fetch permissions", err);
      setError("Failed to load permissions");
      setPermissions(new Set());
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    refreshPermissions();
  }, [refreshPermissions]);

  const hasPermission = useCallback(
    (code: string): boolean => {
      return permissions.has(code);
    },
    [permissions]
  );

  const hasAnyPermission = useCallback(
    (...codes: string[]): boolean => {
      return codes.some((code) => permissions.has(code));
    },
    [permissions]
  );

  const hasAllPermissions = useCallback(
    (...codes: string[]): boolean => {
      return codes.every((code) => permissions.has(code));
    },
    [permissions]
  );

  return (
    <PermissionContext.Provider
      value={{
        permissions,
        loading,
        error,
        hasPermission,
        hasAnyPermission,
        hasAllPermissions,
        refreshPermissions,
      }}
    >
      {children}
    </PermissionContext.Provider>
  );
};

export { PermissionContext, PermissionProvider };
export default PermissionProvider;

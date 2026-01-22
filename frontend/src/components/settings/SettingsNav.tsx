import { useMemo, useState } from "react";
import Fuse from "fuse.js";
import SettingsNavItem from "../ui/settings/SettingsNavItem";
import { usePermissions } from "../../hooks/usePermissions";
import { PERMISSIONS } from "../../types/Permission";

export type SettingsNavItemConfig = {
  label: string;
  to: string;
  permissions?: string[]; // Required permissions (any of these)
  searchTexts?: string[];
};

const NAV_ITEMS: SettingsNavItemConfig[] = [
  {
    label: "My Account",
    to: "/settings/my-account",
    // No permissions required - always visible to logged-in users
    searchTexts: [
      "My Account",
      "Profile",
      "Email",
      "Role",
      "Account Security",
      "Update password",
      "New Password",
      "Confirm Password",
    ],
  },
  {
    label: "AI / ML Configuration",
    to: "/settings/ai-ml",
    permissions: [PERMISSIONS.AIML_VIEW, PERMISSIONS.AIML_EDIT],
    searchTexts: [
      "AI / ML Configuration",
      "Model",
      "Generation",
      "Temperature",
      "Safety",
      "Deny",
      "Filters",
      "Langfuse",
    ],
  },
  {
    label: "Integrations",
    to: "/settings/integrations",
    permissions: [PERMISSIONS.INTEGRATION_VIEW],
    searchTexts: [
      "Integrations",
      "External platforms",
      "Sync data",
      "Service Name",
      "Auth Type",
      "Sync Status",
      "Last Synced",
      "Error",
      "Add",
    ],
  },
  {
    label: "Authentication & Users",
    to: "/settings/user-management",
    permissions: [PERMISSIONS.USER_VIEW, PERMISSIONS.AUTH_VIEW],
    searchTexts: [
      "User Management",
      "Authentication",
      "Users",
      "Role",
      "Access",
      "Login",
      "Provider",
      "Google",
      "GitHub",
      "Microsoft",
      "Basic Authentication",
    ],
  },
  // {
  //   label: "Roles & Permissions",
  //   to: "/settings/roles",
  //   permissions: [PERMISSIONS.ROLE_VIEW],
  //   searchTexts: [
  //     "Roles",
  //     "Permissions",
  //     "RBAC",
  //     "Access Control",
  //   ],
  // },
  // {
  //   label: "Permission Sets",
  //   to: "/settings/permission-sets",
  //   permissions: [PERMISSIONS.PERMISSION_SET_VIEW],
  //   searchTexts: [
  //     "Permission Sets",
  //     "Permissions",
  //     "Groups",
  //     "RBAC",
  //   ],
  // },
  {
    label: "Configuration History",
    to: "/settings/config-history",
    permissions: [PERMISSIONS.HISTORY_VIEW],
    searchTexts: [
      "Configuration History",
      "Audit",
      "Audit Trail",
      "History",
      "Rollback",
      "Version",
      "Changes",
      "Logs",
    ],
  },
];

type SettingsNavProps = {
  onNavigate?: () => void;
};

const SettingsNav = ({ onNavigate }: SettingsNavProps) => {
  const { hasAnyPermission, loading: permissionsLoading } = usePermissions();
  const [query, setQuery] = useState("");

  const items = useMemo(() => {
    // While loading permissions, only show items with no permission requirements
    if (permissionsLoading) {
      return NAV_ITEMS.filter((item) => !item.permissions);
    }
    // Filter items based on user's permissions
    return NAV_ITEMS.filter(
      (item) => !item.permissions || hasAnyPermission(...item.permissions)
    );
  }, [hasAnyPermission, permissionsLoading]);

  const fuse = useMemo(() => {
    return new Fuse(items, {
      keys: ["label", "searchTexts"],
      threshold: 0.35,
      ignoreLocation: true,
    });
  }, [items]);

  const filteredItems = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return items;
    return fuse.search(normalized).map((result) => result.item);
  }, [fuse, items, query]);

  return (
    <nav className="w-full">
      <div className=" mb-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search settings"
          className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm focus:border-gray-400 focus:outline-none focus:ring-0"
        />
      </div>
      <div className="space-y-1">
        {filteredItems.map((item) => (
          <SettingsNavItem
            key={item.to}
            label={item.label}
            to={item.to}
            
            highlightQuery={query}
            onNavigate={onNavigate}
          />
        ))}
        {filteredItems.length === 0 ? (
          <p className="text-xs text-gray-500 px-3 py-2">No matches</p>
        ) : null}
      </div>
    </nav>
  );
};

export default SettingsNav;

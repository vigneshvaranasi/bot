import { useMemo, useState } from "react";
import Fuse from "fuse.js";
import SettingsNavItem from "../ui/settings/SettingsNavItem";
import { useAuthContext } from "../../hooks/useAuthContext";

export type SettingsNavItemConfig = {
  label: string;
  to: string;
  adminOnly?: boolean;
  searchTexts?: string[];
};

const NAV_ITEMS: SettingsNavItemConfig[] = [
  {
    label: "My Account",
    to: "/settings/my-account",
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
  //   { label: "System Configuration", to: "/settings/system", adminOnly: true },
  {
    label: "AI / ML Configuration",
    to: "/settings/ai-ml",
    adminOnly: true,
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
    adminOnly: true,
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
    adminOnly: true,
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
  //   { label: "Audit & Logs", to: "/settings/audit", adminOnly: true },
];

type SettingsNavProps = {
  onNavigate?: () => void;
};

const SettingsNav = ({ onNavigate }: SettingsNavProps) => {
  const { user } = useAuthContext();
  //   const location = useLocation();
  const [query, setQuery] = useState("");

  const items = useMemo(() => {
    const isAdmin = user?.role === "admin";
    return NAV_ITEMS.filter((item) => !item.adminOnly || isAdmin);
  }, [user]);

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

import { NavLink } from "react-router-dom";

export type SettingsNavItemProps = {
  label: string;
  to: string;
  disabled?: boolean;
  badge?: string;
  highlightQuery?: string;
  onNavigate?: () => void;
};

const baseClasses =
  "flex items-center justify-between px-3 py-2 rounded-md text-sm transition-colors";

const activeClasses = "bg-gray-200 text-gray-900 font-semibold";
const inactiveClasses = "text-gray-700 hover:bg-gray-100";
const disabledClasses = "text-gray-400 cursor-not-allowed";

const highlightLabel = (label: string, query?: string) => {
  if (!query) return label;
  const idx = label.toLowerCase().indexOf(query.toLowerCase());
  if (idx === -1) return label;
  const before = label.slice(0, idx);
  const match = label.slice(idx, idx + query.length);
  const after = label.slice(idx + query.length);
  return (
    <span>
      {before}
      <span className="font-semibold text-gray-900">{match}</span>
      {after}
    </span>
  );
};

const SettingsNavItem = ({ label, to, disabled, badge, highlightQuery, onNavigate }: SettingsNavItemProps) => {
  if (disabled) {
    return (
      <div className={`${baseClasses} ${disabledClasses}`}>
        <span>{highlightLabel(label, highlightQuery)}</span>
        {badge && <span className="text-[11px] uppercase">{badge}</span>}
      </div>
    );
  }

  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        [
          baseClasses,
          isActive ? activeClasses : inactiveClasses,
        ].join(" ")
      }
      end
      onClick={onNavigate}
    >
      <span>{highlightLabel(label, highlightQuery)}</span>
    </NavLink>
  );
};

export default SettingsNavItem;
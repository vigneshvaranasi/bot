import type { ReactNode } from "react";

export type SettingsHeaderProps = {
  title: string;
  description?: string;
  status?: ReactNode;
};

const SettingsHeader = ({ title, description, status }: SettingsHeaderProps) => {
  return (
    <div className="flex items-start justify-between mb-6">
      <div>
        <h1 className="text-xl font-semibold text-text-primary">{title}</h1>
        {description ? (
          <p className="text-sm text-text-secondary mt-1 max-w-3xl">{description}</p>
        ) : null}
      </div>
      {status}
    </div>
  );
};

export default SettingsHeader;

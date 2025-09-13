import React from 'react';

interface SettingsCardProps {
  title: string;
  children: React.ReactNode;
  className?: string;
}

const SettingsCard: React.FC<SettingsCardProps> = ({
  title,
  children,
  className = ""
}) => {
  return (
    <div className={`bg-white rounded-lg shadow-lg border-2 border-gray-300 p-4 md:p-5 ${className}`}>
      <h2 className="text-lg md:text-xl text-black mb-4">{title}</h2>
      {children}
    </div>
  );
};

export default SettingsCard;
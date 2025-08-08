import React from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'default';

interface BaseButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: ButtonVariant;
  className?: string;
  type?: 'button' | 'submit' | 'reset';
}

const BaseButton: React.FC<BaseButtonProps> = ({
  children,
  onClick,
  variant = 'default',
  className = '',
  type = 'button',
}) => {
  const baseClasses = 'font-semibold py-2 px-6 transition-colors duration-200';

  const variantClasses = {
    primary: 'bg-blue-500 hover:bg-blue-600 text-white rounded-full',
    secondary: 'bg-gray-500 hover:bg-gray-600 text-white text-xs py-1 rounded-md',
    default: 'bg-transparent hover:bg-gray-100 text-gray-700 rounded-full',
  };

  return (
    <button
      type={type}
      onClick={onClick}
      className={`${baseClasses} ${variantClasses[variant]} ${className}`}
    >
      {children}
    </button>
  );
};

interface ActionButtonGroupProps {
  children: React.ReactNode;
  className?: string;
}

const ActionButtonGroup: React.FC<ActionButtonGroupProps> = ({ children, className = '' }) => {
  return (
    <div className={`inline-flex items-center bg-white rounded-full p-1 shadow-md ${className}`}>
      {children}
    </div>
  );
};

export { BaseButton, ActionButtonGroup };


import React from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'default';

interface ButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: ButtonVariant;
  className?: string;
  type?: 'button' | 'submit' | 'reset';
  rounded?: 'full' | 'md' | 'none';
};

export const Button: React.FC<ButtonProps> = ({
  children,
  onClick,
  variant = 'default',
  className = '',
  type = 'button',
  rounded = 'md',
}) => {
  const baseClasses = 'font-semibold py-2 px-6 transition-colors duration-200';

  const variantClasses = {
    primary: 'bg-blue-500 hover:bg-blue-600 text-white',
    secondary: 'bg-gray-500 hover:bg-gray-600 text-white',
    default: 'bg-transparent hover:bg-gray-100 text-gray-700',
  };

  return (
    <button
      type={type}
      onClick={onClick}
      className={`${baseClasses} ${variantClasses[variant]} rounded-${rounded} ${className}`}
    >
      {children}
    </button>
  );
};
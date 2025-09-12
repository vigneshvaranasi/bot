import React from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'default';

interface ButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: ButtonVariant;
  className?: string;
  type?: 'button' | 'submit' | 'reset';
  rounded?: 'full' | 'md' | 'none';
  disabled?: boolean;
  ref?: React.Ref<HTMLButtonElement>;
};

export const Button: React.FC<ButtonProps> = ({
  children,
  onClick,
  variant = 'default',
  className = '',
  type = 'button',
  rounded = 'md',
  disabled = false,
  ref
}) => {
  const baseClasses = 'font-semibold py-2 px-6 transition-colors duration-200';

  const variantClasses = {
    primary: 'bg-blue-500 hover:bg-blue-600 text-white',
    secondary: 'bg-gray-500 hover:bg-gray-600 text-white',
    default: 'bg-transparent text-gray-700',
  };

  return (
    <button
      ref={ref}
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`${baseClasses} ${variantClasses[variant]} rounded-${rounded} ${className} cursor-pointer`}
    >
      {children}
    </button>
  );
};
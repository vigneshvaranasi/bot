import React from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'default' | 'success' | 'danger' | 'ghost';
type ButtonSize = 'sm' | 'md' | 'lg';

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: ButtonVariant;
  size?: ButtonSize;
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
  size = 'md',
  className = '',
  type = 'button',
  rounded = 'md',
  disabled = false,
  ref,
  ...rest
}) => {
  const baseClasses = 'font-semibold transition-colors duration-200 cursor-pointer';

  const sizeClasses: Record<ButtonSize, string> = {
    sm: 'text-xs px-2 py-1',
    md: 'py-2 px-6',
    lg: 'text-base py-2.5 px-8',
  };

  const variantClasses: Record<ButtonVariant, string> = {
    primary: 'bg-blue-500 hover:bg-blue-600 text-white',
    secondary: 'bg-slate-600 hover:bg-slate-700 text-white',
    success: 'bg-green-500 hover:bg-green-600 text-white',
    danger: 'bg-red-500 hover:bg-red-600 text-white',
    ghost: 'bg-blue-50 text-blue-600 hover:bg-blue-100',
    default: 'bg-transparent text-gray-700',
  };

  return (
    <button
      ref={ref}
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`${baseClasses} ${sizeClasses[size]} ${variantClasses[variant]} rounded-${rounded} ${className} disabled:opacity-50 disabled:cursor-not-allowed`}
      {...rest}
    >
      {children}
    </button>
  );
};
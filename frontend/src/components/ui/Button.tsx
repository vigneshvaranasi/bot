import React from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'default' | 'success' | 'danger' | 'ghost' | 'blue' | 'link';
type ButtonSize = 'sm' | 'md' | 'lg';
type ButtonRounded = 'full' | 'md' | 'none' | 'lg' | 'xl';

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
  type?: 'button' | 'submit' | 'reset';
  rounded?: ButtonRounded;
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
  const baseClasses = 'font-semibold shrink-0 transition-colors duration-200 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2';

  const sizeClasses: Record<ButtonSize, string> = {
    sm: 'text-xs px-3 py-1.5',
    md: 'py-2 px-6',
    lg: 'text-base py-2.5 px-8',
  };

  const variantClasses: Record<ButtonVariant, string> = {
    primary: 'bg-accent hover:bg-accent-hover text-text-inverse',
    secondary: 'bg-btn-secondary hover:bg-btn-secondary-hover text-white border border-btn-secondary',
    success: 'bg-btn-success hover:bg-btn-success-hover text-white',
    danger: 'bg-btn-danger hover:bg-btn-danger-hover text-white',
    ghost: 'bg-surface-tertiary text-text-primary hover:bg-surface-hover border border-border-strong',
    blue: 'bg-accent-blue hover:bg-accent-blue-hover text-white',
    link: 'bg-transparent text-accent-blue hover:text-accent-blue-hover underline p-0',
    default: 'bg-transparent text-text-secondary',
  };

  const roundedClasses: Record<ButtonRounded, string> = {
    full: 'rounded-full',
    md: 'rounded-md',
    none: 'rounded-none',
    lg: 'rounded-lg',
    xl: 'rounded-xl',
  };

  return (
    <button
      ref={ref}
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`${baseClasses} ${sizeClasses[size]} ${variantClasses[variant]} ${roundedClasses[rounded]} ${className} disabled:opacity-50 disabled:cursor-not-allowed`}
      {...rest}
    >
      {children}
    </button>
  );
};

import React from "react";
import { FiSearch } from "react-icons/fi";

type InputBoxProps = {
  value: string;
  placeholder?: string;
  onChange: (value: string) => void;
  onKeyDown?: (e: React.KeyboardEvent<HTMLInputElement>) => void;
  showIcon?: boolean;
  className?: string;
  variant?: "chat" | "sidebar";
};

const variantClasses: Record<"chat" | "sidebar", string> = {
  chat: "border border-gray-300 bg-white",
  sidebar: "border-none bg-gray-100 text-sm",
};

const InputBox = ({
  value,
  placeholder = "",
  onChange,
  onKeyDown,
  showIcon = false,
  className = "",
  variant = "chat",
}: InputBoxProps) => {
  const variantClass = variantClasses[variant];

  return (
    <div className={`relative w-full ${className}`}>
      {showIcon && (
        <div className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">
          <FiSearch />
        </div>
      )}
      <input
        type="text"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        className={`w-full px-4 py-2 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 transition ${
          showIcon ? "pl-10" : ""
        } ${variantClass}`}
      />
    </div>
  );
};

export default InputBox;

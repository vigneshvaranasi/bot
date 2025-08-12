import React from 'react';

type CheckboxProps = {
  label?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  id?: string;
  disabled?: boolean;
};

const Checkbox: React.FC<CheckboxProps> = ({ label, checked, onChange, id, disabled }) => {
  return (
    <label
      className={`flex items-center space-x-2 cursor-pointer ${
        disabled ? 'cursor-not-allowed opacity-50' : ''
      }`}
      htmlFor={id}
    >
      <input
        type="checkbox"
        id={id}
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        disabled={disabled}
        className={`
          w-4 h-4 rounded border border-gray-400 
          focus:ring-0 
          accent-[#1B7F9E]
          cursor-pointer
          disabled:cursor-not-allowed disabled:opacity-50
        `}
      />
      {label && <span>{label}</span>}
    </label>
  );
};

export default Checkbox;

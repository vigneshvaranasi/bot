import { useState, useRef, useEffect } from "react";
import caretDownIcon from "../../assets/caretDown.svg";

type DropdownOption = {
  value: string;
  label: string;
};

type DropdownProps = {
  options: DropdownOption[];
  value?: string;
  placeholder?: string;
  onChange: (value?: string) => void;
  disabled?: boolean;
};

const Dropdown = ({
  options,
  value,
  placeholder = "Select...",
  onChange,
  disabled = false,
}: DropdownProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const selectedOption = options.find((option) => option.value === value);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const handleSelect = (optionValue: string) => {
    onChange?.(optionValue);
    setIsOpen(false);
  };

  return (
    <div ref={dropdownRef} className="relative inline-block">
      <button
        type="button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        className={`w-full px-2 py-1 text-sm font-normal
           flex justify-between items-center
           border-b-2 border-border-strong
           bg-surface-primary rounded-bl-md rounded-br-md
           min-w-[200px]
           ${disabled ? "text-text-tertiary cursor-not-allowed bg-surface-tertiary" : "text-text-primary"}`}
      >
        <span className="truncate">
          {selectedOption ? selectedOption.label : placeholder}
        </span>
        <img
          src={caretDownIcon}
          alt="caret down"
          className={`w-5 h-5 ml-2 text-text-secondary transition-transform flex-shrink-0 icon-adaptive ${
        isOpen ? "rotate-180" : ""
          }`}
        />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 w-full mt-1 bg-surface-primary border border-border-default rounded-md shadow-dropdown z-50">
          {options.map((option) => (
            <div
              key={option.value}
              onClick={() => handleSelect(option.value)}
              className="px-3 py-2 text-sm text-text-primary hover:bg-surface-tertiary cursor-pointer"
            >
              {option.label}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default Dropdown;
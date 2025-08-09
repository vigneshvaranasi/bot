import { useState } from "react";
import caretDownIcon from "../../assets/caretDown.svg";

type DropdownOption = {
  value: string;
  label: string;
};

type DropdownProps = {
  options: DropdownOption[];
  value?: string;
  placeholder?: string;
  onChange: (value: any) => void
};

const Dropdown = ({
  options,
  value,
  placeholder = "Select...",
  onChange,
}: DropdownProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const selectedOption = options.find((option) => option.value === value);

  const handleSelect = (optionValue: string) => {
    onChange?.(optionValue);
    setIsOpen(false);
  };

  return (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-2 py-1 text-sm font-normal text-gray-800 
                   flex justify-between items-center 
                   border-b-2 border-gray-400 
                   bg-white rounded-bl-md rounded-br-md"
      >
        <span>
          {selectedOption ? selectedOption.label : placeholder}
        </span>
        <img
          src={caretDownIcon}
          alt="caret down"
          className={`w-5 h-5 ml-2 text-gray-700 transition-transform ${
            isOpen ? "rotate-180" : ""
          }`}
        />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-md z-10">
          {options.map((option) => (
            <div
              key={option.value}
              onClick={() => handleSelect(option.value)}
              className="px-3 py-2 text-sm text-gray-800 hover:bg-gray-100 cursor-pointer"
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
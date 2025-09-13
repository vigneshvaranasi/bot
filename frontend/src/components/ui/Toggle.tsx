import React from "react";

type ToggleProps = {
  enabled: boolean;
  onChange: (enabled: boolean) => void;
  label?: string;
  id?: string;
};

const Toggle: React.FC<ToggleProps> = ({ enabled, onChange, label, id }) => {
  return (
    <label
      htmlFor={id}
      className="flex items-center space-x-3 cursor-pointer select-none"
    >
      {label && <span>{label}</span>}

        <div
          className={`relative w-[40px] h-[22px] rounded-[2px] p-[2px] bg-white transition-colors duration-200 border-2 ${enabled ? "border-[#1B7F9E]" : "border-[#72777D]"}`}
        >
        <input
          id={id}
          type="checkbox"
          checked={enabled}
          onChange={(e) => onChange(e.target.checked)}
          className="sr-only peer"
        />

          <div
            className={`absolute top-[1px] bottom-[1px] flex items-center justify-center w-4 rounded-[2px] transition-all duration-200
              ${enabled ? "left-[19px] bg-[#1B7F9E]" : "left-[2px] bg-gray-600"}`}
          >
          {enabled && (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="w-5 h-5 text-white"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="3"
              strokeLinecap="butt"
              strokeLinejoin="miter"
            >
              <polyline points="20 6 9 17 4 12" />
            </svg>
          )}
        </div>
      </div>
    </label>
  );
};

export default Toggle;

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
        className="relative"
        style={{
          width: "52px",
          height: "30px",
          borderRadius: "2px",
          border: `2px solid ${enabled ? "#1B7F9E" : "#72777D"}`,
          padding: "2px",
          backgroundColor: "#FFFFFF",
          transition: "border-color 0.2s ease",
        }}
      >
        <input
          id={id}
          type="checkbox"
          checked={enabled}
          onChange={(e) => onChange(e.target.checked)}
          className="sr-only peer"
        />

        <div
          className={`absolute top-[1px] bottom-[1px] flex items-center justify-center w-6 rounded-[2px] transition-all duration-200
            ${enabled ? "left-[23px] bg-[#1B7F9E]" : "left-[1px] bg-gray-600"}`}
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

import { useState, useRef, useEffect, useLayoutEffect, useCallback } from "react";
import { createPortal } from "react-dom";
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
  className?: string;
};

type MenuPosition = {
  top: number;
  left: number;
  width: number;
  openUp: boolean;
  maxHeight: number;
};

const MENU_GAP = 4;
const VIEWPORT_PADDING = 8;

const Dropdown = ({
  options,
  value,
  placeholder = "Select...",
  onChange,
  disabled = false,
  className = "",
}: DropdownProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const [menuPos, setMenuPos] = useState<MenuPosition | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const selectedOption = options.find((option) => option.value === value);

  const computePosition = useCallback(() => {
    const trigger = triggerRef.current;
    if (!trigger) return;

    const rect = trigger.getBoundingClientRect();
    const viewportH = window.innerHeight;
    const spaceBelow = viewportH - rect.bottom - VIEWPORT_PADDING;
    const spaceAbove = rect.top - VIEWPORT_PADDING;
    const openUp = spaceBelow < 160 && spaceAbove > spaceBelow;
    const maxHeight = Math.max(120, openUp ? spaceAbove - MENU_GAP : spaceBelow - MENU_GAP);

    setMenuPos({
      top: openUp ? rect.top - MENU_GAP : rect.bottom + MENU_GAP,
      left: rect.left,
      width: rect.width,
      openUp,
      maxHeight,
    });
  }, []);

  // Close dropdown when clicking outside
  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (
        triggerRef.current?.contains(target) ||
        menuRef.current?.contains(target)
      ) {
        return;
      }
      setIsOpen(false);
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  useLayoutEffect(() => {
    if (!isOpen) {
      setMenuPos(null);
      return;
    }
    computePosition();

    const handle = () => computePosition();
    window.addEventListener("resize", handle);
    window.addEventListener("scroll", handle, true);
    return () => {
      window.removeEventListener("resize", handle);
      window.removeEventListener("scroll", handle, true);
    };
  }, [isOpen, computePosition]);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setIsOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [isOpen]);

  const handleSelect = (optionValue: string) => {
    onChange?.(optionValue);
    setIsOpen(false);
  };

  return (
    <div className={`relative inline-block ${className}`}>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => !disabled && setIsOpen((prev) => !prev)}
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

      {isOpen && menuPos &&
        createPortal(
          <div
            ref={menuRef}
            style={{
              position: "fixed",
              top: menuPos.openUp ? undefined : menuPos.top,
              bottom: menuPos.openUp ? window.innerHeight - menuPos.top : undefined,
              left: menuPos.left,
              width: menuPos.width,
              maxHeight: menuPos.maxHeight,
            }}
            className="bg-surface-primary border border-border-default rounded-md shadow-dropdown z-[100] overflow-y-auto"
          >
            {options.map((option) => (
              <div
                key={option.value}
                onClick={() => handleSelect(option.value)}
                className="px-3 py-2 text-sm text-text-primary hover:bg-surface-tertiary cursor-pointer"
              >
                {option.label}
              </div>
            ))}
          </div>,
          document.body
        )}
    </div>
  );
};

export default Dropdown;
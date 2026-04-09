import { useEffect, useRef, type ReactNode } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Button } from "./Button";

type ModalProps = {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg" | "xl" | "2xl" | "3xl" | "4xl" | "full";
  closeOnOverlayClick?: boolean;
  closeOnEsc?: boolean;
  bodyOverflowVisible?: boolean;
};

const sizeClasses = {
  sm: "max-w-sm",
  md: "max-w-md",
  lg: "max-w-lg",
  xl: "max-w-xl",
  "2xl": "max-w-2xl",
  "3xl": "max-w-3xl",
  "4xl": "max-w-4xl",
  full: "max-w-5xl",
};

export default function Modal({
  isOpen,
  onClose,
  title,
  children,
  footer,
  size = "md",
  closeOnOverlayClick = true,
  closeOnEsc = true,
  bodyOverflowVisible = false,
}: ModalProps) {
  const modalRef = useRef<HTMLDivElement>(null);

  // Handle escape key
  useEffect(() => {
    if (!isOpen || !closeOnEsc) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose, closeOnEsc]);

  // Lock body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  // Focus trap - focus modal when opened
  useEffect(() => {
    if (isOpen && modalRef.current) {
      modalRef.current.focus();
    }
  }, [isOpen]);

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (closeOnOverlayClick && e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-title"
        >
          {/* Overlay */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 bg-black/50"
            onClick={handleOverlayClick}
          />

          {/* Modal */}
          <motion.div
            ref={modalRef}
            tabIndex={-1}
            initial={{ opacity: 0, scale: 0.97 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.97 }}
            transition={{ duration: 0.15 }}
            className={`relative bg-surface-primary rounded-lg shadow-xl w-full mx-4 ${sizeClasses[size]} max-h-[90vh] flex flex-col`}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-border-default">
              <h2 id="modal-title" className="text-lg font-semibold text-text-primary">
                {title}
              </h2>
              <button
                type="button"
                onClick={onClose}
                className="text-text-tertiary hover:text-text-primary transition-colors p-1 rounded-md hover:bg-surface-tertiary"
                aria-label="Close modal"
              >
                <svg
                  className="w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>

            {/* Body */}
            <div className={`flex-1 px-4 py-4 ${bodyOverflowVisible ? "overflow-visible" : "overflow-y-auto"}`}>{children}</div>

            {/* Footer */}
            {footer && (
              <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-border-default bg-surface-secondary rounded-b-lg">
                {footer}
              </div>
            )}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}

// Convenience component for confirmation modals
type ConfirmModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string | ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  confirmVariant?: "primary" | "secondary" | "danger";
  isLoading?: boolean;
};

export function ConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  confirmVariant = "primary",
  isLoading = false,
}: ConfirmModalProps) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={title}
      size="sm"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={isLoading}>
            {cancelLabel}
          </Button>
          <Button
            variant={confirmVariant}
            onClick={onConfirm}
            disabled={isLoading}
          >
            {isLoading ? "..." : confirmLabel}
          </Button>
        </>
      }
    >
      <div className="text-sm text-text-secondary">{message}</div>
    </Modal>
  );
}

// Convenience component for input modals (e.g., reason input)
type InputModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (value: string) => void;
  title: string;
  label: string;
  placeholder?: string;
  submitLabel?: string;
  cancelLabel?: string;
  isLoading?: boolean;
  required?: boolean;
  multiline?: boolean;
};

export function InputModal({
  isOpen,
  onClose,
  onSubmit,
  title,
  label,
  placeholder = "",
  submitLabel = "Submit",
  cancelLabel = "Cancel",
  isLoading = false,
  required = false,
  multiline = false,
}: InputModalProps) {
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement>(null);

  // Focus input when modal opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  const doSubmit = () => {
    const value = inputRef.current?.value?.trim() || "";
    if (required && !value) return;
    onSubmit(value);
  };

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    doSubmit();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={title}
      size="md"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={isLoading}>
            {cancelLabel}
          </Button>
          <Button
            variant="primary"
            onClick={doSubmit}
            disabled={isLoading}
          >
            {isLoading ? "..." : submitLabel}
          </Button>
        </>
      }
    >
      <form onSubmit={handleFormSubmit}>
        <label className="block text-sm font-medium text-text-secondary mb-1">
          {label}
          {required && <span className="text-danger-text ml-1">*</span>}
        </label>
        {multiline ? (
          <textarea
            ref={inputRef as React.RefObject<HTMLTextAreaElement>}
            placeholder={placeholder}
            className="w-full px-3 py-2 border border-border-default bg-surface-primary text-text-primary rounded-md focus:outline-none focus:ring-1 focus:ring-accent-blue resize-none"
            rows={3}
          />
        ) : (
          <input
            ref={inputRef as React.RefObject<HTMLInputElement>}
            type="text"
            placeholder={placeholder}
            className="w-full px-3 py-2 border border-border-default bg-surface-primary text-text-primary rounded-md focus:outline-none focus:ring-1 focus:ring-accent-blue"
          />
        )}
      </form>
    </Modal>
  );
}

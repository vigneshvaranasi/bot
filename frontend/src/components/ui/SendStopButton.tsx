import React from 'react';

interface SendStopButtonProps {
  isLoading: boolean;
  disabled?: boolean;
  onSend: () => void;
  onStop: () => void;
  className?: string;
  inputValue?: string;
}

export const SendStopButton: React.FC<SendStopButtonProps> = ({
  isLoading,
  disabled = false,
  onSend,
  onStop,
  className = '',
  inputValue = '',
}) => {
  const handleClick = () => {
    if (isLoading) {
      onStop();
    } else {
      onSend();
    }
  };

  const isDisabled = disabled || (!isLoading && !inputValue.trim());

  return (
    <button
      onClick={handleClick}
      disabled={isDisabled}
      className={`font-semibold p-3 transition-colors duration-200 bg-gray-500 hover:bg-gray-600 text-white rounded-xl flex items-center justify-center w-11 h-11 ${className} ${
        isDisabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
      }`}
    >
      {isLoading ? (
        <svg 
          className="w-20 h-20"
          fill="currentColor" 
          viewBox="0 0 24 24"
        >
          <rect x="2" y="2" width="20" height="20" rx="2" />
        </svg>
      ) : (
        <svg 
          className="w-20 h-20" 
          fill="currentColor" 
          viewBox="0 0 24 24"
        >
          <path d="M12 1L3 12h7v10h4V12h7L12 1z" />
        </svg>
      )}
    </button>
  );
};
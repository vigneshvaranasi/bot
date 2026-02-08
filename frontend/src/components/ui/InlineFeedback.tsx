import { useState, useRef, useEffect } from 'react';
import type { FeedbackType } from '../../types';

const NEGATIVE_REASONS = [
  'Incorrect or outdated information',
  'Referenced wrong incident',
  'Missing steps or incomplete',
  'Not relevant to my query',
  'Unclear explanation',
  'Other',
];

const POSITIVE_REASONS = [
  'Accurate information',
  'Helpful resolution steps',
  'Clear and well explained',
  'Saved me time',
  'Other',
];

interface InlineFeedbackProps {
  feedbackType: FeedbackType;
  onSubmit: (reason: string) => void;
  onCancel: () => void;
  isLoading?: boolean;
}

export function InlineFeedback({
  feedbackType,
  onSubmit,
  onCancel,
  isLoading = false,
}: InlineFeedbackProps) {
  const [selectedReason, setSelectedReason] = useState<string | null>(null);
  const [customReason, setCustomReason] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const isPositive = feedbackType === 'positive';
  const reasons = isPositive ? POSITIVE_REASONS : NEGATIVE_REASONS;

  useEffect(() => {
    setSelectedReason(null);
    setCustomReason('');
  }, [feedbackType]);

  useEffect(() => {
    if (selectedReason === 'Other' && inputRef.current) {
      inputRef.current.focus();
    }
  }, [selectedReason]);

  const handleSelect = (reason: string) => {
    setSelectedReason(reason === selectedReason ? null : reason);
    if (reason !== 'Other') setCustomReason('');
  };

  const handleSubmit = () => {
    const finalReason = selectedReason === 'Other' ? customReason.trim() : selectedReason || '';
    onSubmit(finalReason);
  };

  const canSubmit = selectedReason && (selectedReason !== 'Other' || customReason.trim());

  return (
    <div className="mt-4 ml-1 max-w-md">
      <div className="flex items-start justify-between mb-1">
        <h3 className="text-base font-medium text-gray-900">
          {isPositive ? 'Thank you!' : 'Thank you!'}
        </h3>
        <button
          onClick={onCancel}
          className="text-gray-500 hover:text-gray-700 hover:bg-gray-100 p-1 -mr-1 -mt-1 rounded cursor-pointer transition-colors"
          aria-label="Close"
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      
      <p className="text-sm text-gray-500 mb-4">
        Your feedback helps make responses better for everyone.
      </p>

      <div className="mb-4">
        {reasons.map((reason) => (
          <button
            key={reason}
            onClick={() => handleSelect(reason)}
            disabled={isLoading}
            className={`
              w-full text-left px-1 py-2.5 text-sm flex items-center justify-between
              transition-colors rounded
              ${isLoading ? 'opacity-50 cursor-not-allowed' : 'hover:bg-gray-100 cursor-pointer'}
              ${selectedReason === reason ? 'bg-gray-50' : ''}
            `}
          >
            <span className="text-gray-700">{reason}</span>
            {selectedReason === reason && (
              <svg className="w-5 h-5 text-gray-700 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            )}
          </button>
        ))}
      </div>

      {selectedReason === 'Other' && (
        <div className="mb-4">
          <input
            ref={inputRef}
            type="text"
            value={customReason}
            onChange={(e) => setCustomReason(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && canSubmit && handleSubmit()}
            placeholder="Provide additional feedback"
            disabled={isLoading}
            className="w-full px-4 py-3 text-sm bg-gray-100 border-0 rounded-lg 
                       focus:outline-none focus:ring-2 focus:ring-gray-400
                       placeholder-gray-500"
          />
        </div>
      )}

      <button
        onClick={handleSubmit}
        disabled={!canSubmit || isLoading}
        className={`
          w-full py-2 text-sm font-medium rounded-lg transition-all cursor-pointer
          ${canSubmit && !isLoading
            ? 'bg-gray-900 text-white hover:bg-gray-800'
            : 'bg-gray-200 text-gray-400 cursor-not-allowed'
          }
        `}
      >
        {isLoading ? 'Submitting...' : 'Submit'}
      </button>

      <p className="mt-4 text-xs text-gray-400">
        Feedback is used to improve AI responses.
      </p>
    </div>
  );
}

export default InlineFeedback;
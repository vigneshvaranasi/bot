import { useState, useRef, useId } from 'react';
import {
  useFloating,
  useInteractions,
  useHover,
  useFocus,
  useClick,
  useDismiss,
  useRole,
  offset,
  flip,
  shift,
  arrow,
  FloatingPortal,
  FloatingArrow,
  type Placement,
} from '@floating-ui/react';

type InfoHintProps = {
  text: string;
  icon?: string;
  onClick?: () => void;
  position?: 'top' | 'bottom' | 'left' | 'right';
  gap?: number;
};

const InfoHint: React.FC<InfoHintProps> = ({
  text,
  onClick,
  position = 'top',
  gap = 6,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const arrowRef = useRef<SVGSVGElement>(null);
  const tooltipId = useId();

  const { refs, floatingStyles, context } = useFloating({
    open: isOpen,
    onOpenChange: setIsOpen,
    placement: position as Placement,
    middleware: [
      offset(gap),
      flip(),
      shift({ padding: 8 }),
      arrow({ element: arrowRef }),
    ],
  });

  const { getReferenceProps, getFloatingProps } = useInteractions([
    useHover(context, { move: false, delay: { open: 150 } }),
    useFocus(context),
    useClick(context),
    useDismiss(context),
    useRole(context, { role: 'tooltip' }),
  ]);

  return (
    <>
      <button
        type="button"
        ref={refs.setReference}
        aria-describedby={isOpen ? tooltipId : undefined}
        onClick={onClick}
        className="inline-flex items-center justify-center p-0 bg-transparent border-0 text-blue-400 hover:text-blue-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-1 rounded-full cursor-pointer transition-colors"
        {...getReferenceProps()}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className="w-4 h-4"
        >
          <path
            fillRule="evenodd"
            d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      {isOpen && (
        <FloatingPortal>
          <div
            ref={refs.setFloating}
            id={tooltipId}
            style={floatingStyles}
            className="z-40 max-w-xs bg-gray-900 text-white text-xs rounded-lg px-3 py-2 shadow-lg"
            {...getFloatingProps()}
          >
            {text}
            <FloatingArrow ref={arrowRef} context={context} fill="#111827" width={10} height={5} />
          </div>
        </FloatingPortal>
      )}
    </>
  );
};

export default InfoHint;

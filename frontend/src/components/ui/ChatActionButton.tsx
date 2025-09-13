import { useState } from "react";
import retryIcon from "../../assets/retry.svg";
import thumbsUpIcon from "../../assets/thumbsUp.svg";
import thumbsUpFilledIcon from "../../assets/thumbsUpfill.svg";
import thumbsDownIcon from "../../assets/thumbsDown.svg";
import thumbsDownFilledIcon from "../../assets/thumbsDownfill.svg";

interface ChatActionButtonProps {
  type: "retry" | "thumbsUp" | "thumbsDown";
  active?: boolean;
  loading?: boolean;
  onClick?: () => void;
}

const icons: Record<string, { default: string; active?: string }> = {
  retry: { default: retryIcon },
  thumbsUp: { default: thumbsUpIcon, active: thumbsUpFilledIcon },
  thumbsDown: { default: thumbsDownIcon, active: thumbsDownFilledIcon },
};

const tooltips: Record<string, string> = {
  retry: "Retry",
  thumbsUp: "Like",
  thumbsDown: "Dislike",
};

export const ChatActionButton: React.FC<ChatActionButtonProps> = ({
  type,
  active: activeProp,
  loading,
  onClick,
}) => {
  const [active, setActive] = useState(false);

  const iconSet = icons[type];
  const tooltip = tooltips[type];

  const isActive = type === "retry" ? false : activeProp ?? active;

  const icon =
    type === "retry"
      ? iconSet.default
      : isActive && iconSet.active
      ? iconSet.active
      : iconSet.default;

  function handleClick() {
    if (type !== "retry") {
      setActive((prev) => !prev);
    }
    if (onClick) onClick();
  }

  return (
    <div className="relative group inline-flex">
      <button
        onClick={handleClick}
        disabled={loading && type === "retry"}
        aria-label={tooltip}
        className="flex items-center justify-center p-1
             text-gray-600 hover:text-black hover:bg-gray-100
             disabled:opacity-50 disabled:cursor-not-allowed
             rounded-sm"
      >
        <img
          src={icon}
          alt={tooltip}
          className={`${type === "retry" ? "h-4 w-4" : "h-6 w-6"} ${
            loading && type === "retry" ? "animate-spin" : ""
          }`}
        />
      </button>

      {/* Tooltip */}
      <div
        className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2
                   opacity-0 group-hover:opacity-100 pointer-events-none
                   bg-black text-white text-xs rounded px-2 py-1
                   transition-opacity duration-200 whitespace-nowrap"
      >
        {loading && type === "retry" ? "Retrying..." : tooltip}
      </div>
    </div>
  );
};

export const ChatActions = () => {
  return (
    <div className="flex items-center gap-0.5">
      <ChatActionButton type="retry" />
      <ChatActionButton type="thumbsUp" />
      <ChatActionButton type="thumbsDown" />
    </div>
  );
};

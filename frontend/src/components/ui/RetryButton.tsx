import { Button } from "../../components/ui/Button";
import retryIcon from "../../assets/retry.svg";

interface RetryButtonProps {
  onRetry: () => void;
  loading?: boolean;
}

export const RetryButton: React.FC<RetryButtonProps> = ({ onRetry, loading }) => {
  return (
    <Button
      onClick={onRetry}
      disabled={loading}
      aria-label="Retry action"
      className="flex items-center justify-center gap-2 rounded-full px-4 py-2 
                 text-sm font-medium text-gray-600 
                 hover:text-black hover:bg-gray-100 
                 disabled:opacity-50 disabled:cursor-not-allowed 
                 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-400"
    >
      <img
        src={retryIcon}
        alt="Retry"
        className={`h-4 w-4 ${loading ? "animate-spin" : ""}`}
      />
      <span>{loading ? "Retrying..." : "Retry"}</span>
    </Button>
  );
};

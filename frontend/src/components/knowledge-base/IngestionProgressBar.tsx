type Props = {
  batch: number;
  totalBatches: number;
  message: string;
  isComplete?: boolean;
  isError?: boolean;
};

const IngestionProgressBar = ({ batch, totalBatches, message, isComplete, isError }: Props) => {
  const percentage = totalBatches > 0 ? Math.round((batch / totalBatches) * 100) : 0;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs text-text-secondary">
        <span>{message}</span>
        <span>
          {batch}/{totalBatches} batches ({percentage}%)
        </span>
      </div>

      <div className="w-full bg-surface-hover rounded-full h-2.5 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-300 ${
            isError
              ? "bg-danger-text"
              : isComplete
                ? "bg-success-text"
                : "bg-accent-blue"
          }`}
          style={{ width: `${isComplete ? 100 : percentage}%` }}
        />
      </div>

      {isComplete && (
        <p className="text-xs text-success-text font-medium">Ingestion complete!</p>
      )}
      {isError && (
        <p className="text-xs text-danger-text font-medium">Ingestion failed.</p>
      )}
    </div>
  );
};

export default IngestionProgressBar;

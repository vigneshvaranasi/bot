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
      <div className="flex items-center justify-between text-xs text-gray-600">
        <span>{message}</span>
        <span>
          {batch}/{totalBatches} batches ({percentage}%)
        </span>
      </div>

      <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-300 ${
            isError
              ? "bg-red-500"
              : isComplete
                ? "bg-green-500"
                : "bg-blue-500"
          }`}
          style={{ width: `${isComplete ? 100 : percentage}%` }}
        />
      </div>

      {isComplete && (
        <p className="text-xs text-green-700 font-medium">Ingestion complete!</p>
      )}
      {isError && (
        <p className="text-xs text-red-700 font-medium">Ingestion failed.</p>
      )}
    </div>
  );
};

export default IngestionProgressBar;

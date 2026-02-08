import React from "react";

// Common page size options
export const DEFAULT_PAGE_SIZE_OPTIONS = [10, 15, 25, 50];

type PageSizeSelectorProps = {
  pageSize: number;
  onPageSizeChange: (size: number) => void;
  options?: number[];
  disabled?: boolean;
  className?: string;
  label?: string;
};

/**
 * Dropdown to select number of rows per page.
 */
export const PageSizeSelector: React.FC<PageSizeSelectorProps> = ({
  pageSize,
  onPageSizeChange,
  options = DEFAULT_PAGE_SIZE_OPTIONS,
  disabled = false,
  className = "",
  label = "Rows per page:",
}) => {
  return (
    <div className={`flex items-center gap-2 text-xs text-gray-600 ${className}`}>
      <span>{label}</span>
      <select
        value={pageSize}
        onChange={(e) => onPageSizeChange(Number(e.target.value))}
        disabled={disabled}
        className={`px-2 py-1 border border-gray-300 rounded text-xs bg-white focus:outline-none focus:ring-1 focus:ring-blue-500 ${
          disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"
        }`}
      >
        {options.map((size) => (
          <option key={size} value={size}>
            {size}
          </option>
        ))}
      </select>
    </div>
  );
};

type PaginationProps = {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  totalItems?: number;
  pageSize?: number;
  onPageSizeChange?: (size: number) => void;
  pageSizeOptions?: number[];
  showPageInfo?: boolean;
  showPageSizeSelector?: boolean;
  disabled?: boolean;
  className?: string;
};

/**
 * Reusable pagination component with page numbers and navigation.
 */
export const Pagination: React.FC<PaginationProps> = ({
  currentPage,
  totalPages,
  onPageChange,
  totalItems,
  pageSize,
  onPageSizeChange,
  pageSizeOptions = DEFAULT_PAGE_SIZE_OPTIONS,
  showPageInfo = true,
  showPageSizeSelector = true,
  disabled = false,
  className = "",
}) => {
  // Don't render if no pagination needed and no page size selector
  if (totalPages <= 1 && !showPageSizeSelector) return null;

  const getPageNumbers = (): (number | "...")[] => {
    const pages: (number | "...")[] = [];
    const maxVisiblePages = 5;

    if (totalPages <= maxVisiblePages) {
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      // Always show first page
      pages.push(1);

      if (currentPage > 3) {
        pages.push("...");
      }

      // Show pages around current
      const start = Math.max(2, currentPage - 1);
      const end = Math.min(totalPages - 1, currentPage + 1);

      for (let i = start; i <= end; i++) {
        pages.push(i);
      }

      if (currentPage < totalPages - 2) {
        pages.push("...");
      }

      // Always show last page
      pages.push(totalPages);
    }

    return pages;
  };

  const startItem = totalItems && pageSize ? (currentPage - 1) * pageSize + 1 : null;
  const endItem =
    totalItems && pageSize ? Math.min(currentPage * pageSize, totalItems) : null;

  return (
    <div className={`flex items-center justify-between gap-4 flex-wrap ${className}`}>
      <div className="flex items-center gap-4">
        {showPageSizeSelector && onPageSizeChange && pageSize && (
          <PageSizeSelector
            pageSize={pageSize}
            onPageSizeChange={onPageSizeChange}
            options={pageSizeOptions}
            disabled={disabled}
          />
        )}
        {showPageInfo && totalItems !== undefined && (
          <div className="text-xs text-gray-500">
            {startItem !== null && endItem !== null
              ? `Showing ${startItem}-${endItem} of ${totalItems}`
              : `${totalItems} total`}
          </div>
        )}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center gap-1">
        {/* Previous button */}
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={disabled || currentPage === 1}
          className={`px-2 py-1 text-xs rounded border ${
            currentPage === 1 || disabled
              ? "border-gray-200 text-gray-300 cursor-not-allowed"
              : "border-gray-300 text-gray-600 hover:bg-gray-100"
          }`}
          aria-label="Previous page"
        >
          ← Prev
        </button>

        {/* Page numbers */}
        {getPageNumbers().map((page, index) =>
          page === "..." ? (
            <span key={`ellipsis-${index}`} className="px-2 py-1 text-xs text-gray-400">
              ...
            </span>
          ) : (
            <button
              key={page}
              onClick={() => onPageChange(page)}
              disabled={disabled}
              className={`px-2.5 py-1 text-xs rounded border ${
                currentPage === page
                  ? "border-blue-500 bg-blue-500 text-white"
                  : disabled
                  ? "border-gray-200 text-gray-300 cursor-not-allowed"
                  : "border-gray-300 text-gray-600 hover:bg-gray-100"
              }`}
              aria-current={currentPage === page ? "page" : undefined}
            >
              {page}
            </button>
          )
        )}

        {/* Next button */}
        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={disabled || currentPage === totalPages}
          className={`px-2 py-1 text-xs rounded border ${
            currentPage === totalPages || disabled
              ? "border-gray-200 text-gray-300 cursor-not-allowed"
              : "border-gray-300 text-gray-600 hover:bg-gray-100"
          }`}
          aria-label="Next page"
        >
          Next →
        </button>
      </div>
      )}
    </div>
  );
};

type LoadMoreButtonProps = {
  onClick: () => void;
  loading?: boolean;
  hasMore: boolean;
  loadedCount: number;
  totalCount?: number;
  className?: string;
};

/**
 * Load More button for infinite scroll patterns.
 */
export const LoadMoreButton: React.FC<LoadMoreButtonProps> = ({
  onClick,
  loading = false,
  hasMore,
  loadedCount,
  totalCount,
  className = "",
}) => {
  if (!hasMore) return null;

  return (
    <div className={`flex flex-col items-center gap-2 py-3 ${className}`}>
      {totalCount !== undefined && (
        <span className="text-xs text-gray-400">
          Showing {loadedCount} of {totalCount}
        </span>
      )}
      <button
        onClick={onClick}
        disabled={loading}
        className="px-4 py-1.5 text-xs text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-full transition-colors disabled:opacity-50"
      >
        {loading ? "Loading..." : "Load More"}
      </button>
    </div>
  );
};

export default Pagination;

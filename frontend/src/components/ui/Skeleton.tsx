import { type FC } from "react";

interface SkeletonProps {
  className?: string;
  width?: string | number;
  height?: string | number;
  rounded?: "none" | "sm" | "md" | "lg" | "full";
  shimmer?: boolean;
}

/**
 * Base skeleton component with shimmer animation
 */
export const Skeleton: FC<SkeletonProps> = ({
  className = "",
  width,
  height,
  rounded = "md",
  shimmer = true,
}) => {
  const roundedClasses = {
    none: "rounded-none",
    sm: "rounded-sm",
    md: "rounded-md",
    lg: "rounded-lg",
    full: "rounded-full",
  };

  return (
    <div
      className={`${shimmer ? "skeleton-shimmer" : "animate-pulse bg-gray-200"} ${roundedClasses[rounded]} ${className}`}
      style={{
        width: typeof width === "number" ? `${width}px` : width,
        height: typeof height === "number" ? `${height}px` : height,
      }}
    />
  );
};

interface SkeletonTextProps {
  lines?: number;
  className?: string;
  lineClassName?: string;
}

/**
 * Skeleton for text content with multiple lines
 */
export const SkeletonText: FC<SkeletonTextProps> = ({
  lines = 3,
  className = "",
  lineClassName = "",
}) => {
  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          height={16}
          className={`${lineClassName}`}
          width={i === lines - 1 ? "75%" : "100%"}
        />
      ))}
    </div>
  );
};

interface SkeletonTableRowProps {
  columns: number;
  className?: string;
}

/**
 * Single skeleton table row
 */
export const SkeletonTableRow: FC<SkeletonTableRowProps> = ({
  columns,
  className = "",
}) => {
  return (
    <tr className={`bg-white border-t border-gray-200 ${className}`}>
      {Array.from({ length: columns }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <Skeleton height={16} width={i === 0 ? "80%" : i === columns - 1 ? 60 : "70%"} />
        </td>
      ))}
    </tr>
  );
};

interface SkeletonTableProps {
  rows?: number;
  columns?: number;
  showHeader?: boolean;
  className?: string;
}

/**
 * Skeleton for table content
 */
export const SkeletonTable: FC<SkeletonTableProps> = ({
  rows = 5,
  columns = 4,
  showHeader = true,
  className = "",
}) => {
  return (
    <div className={`overflow-x-auto bg-white rounded-lg border border-gray-300 ${className}`}>
      <table className="min-w-full" style={{ borderSpacing: 0 }}>
        {showHeader && (
          <thead>
            <tr className="bg-gray-50">
              {Array.from({ length: columns }).map((_, i) => (
                <th key={i} className="px-4 py-3 text-left">
                  <Skeleton height={14} width={80} />
                </th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>
          {Array.from({ length: rows }).map((_, rowIndex) => (
            <SkeletonTableRow key={rowIndex} columns={columns} />
          ))}
        </tbody>
      </table>
    </div>
  );
};

interface SkeletonToggleProps {
  className?: string;
  labelWidth?: number | string;
}

/**
 * Skeleton for toggle/switch with label
 */
export const SkeletonToggle: FC<SkeletonToggleProps> = ({
  className = "",
  labelWidth = 120,
}) => {
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <Skeleton height={16} width={labelWidth} />
      <Skeleton height={24} width={44} rounded="full" />
    </div>
  );
};

interface SkeletonInputProps {
  className?: string;
  labelWidth?: number | string;
  showLabel?: boolean;
}

/**
 * Skeleton for input field with optional label
 */
export const SkeletonInput: FC<SkeletonInputProps> = ({
  className = "",
  labelWidth = 100,
  showLabel = true,
}) => {
  return (
    <div className={`space-y-2 ${className}`}>
      {showLabel && <Skeleton height={14} width={labelWidth} />}
      <Skeleton height={40} width="100%" rounded="lg" />
    </div>
  );
};

interface SkeletonDropdownProps {
  className?: string;
  labelWidth?: number | string;
  showLabel?: boolean;
}

/**
 * Skeleton for dropdown/select field
 */
export const SkeletonDropdown: FC<SkeletonDropdownProps> = ({
  className = "",
  labelWidth = 100,
  showLabel = true,
}) => {
  return (
    <div className={`space-y-2 ${className}`}>
      {showLabel && <Skeleton height={14} width={labelWidth} />}
      <Skeleton height={42} width="100%" rounded="lg" />
    </div>
  );
};

interface SkeletonCardProps {
  className?: string;
  showHeader?: boolean;
  showFooter?: boolean;
  contentLines?: number;
}

/**
 * Skeleton for card component
 */
export const SkeletonCard: FC<SkeletonCardProps> = ({
  className = "",
  showHeader = true,
  showFooter = false,
  contentLines = 3,
}) => {
  return (
    <div className={`border border-gray-200 rounded-lg p-4 space-y-4 ${className}`}>
      {showHeader && (
        <div className="flex items-center justify-between">
          <Skeleton height={20} width={150} />
          <Skeleton height={32} width={80} rounded="lg" />
        </div>
      )}
      <SkeletonText lines={contentLines} />
      {showFooter && (
        <div className="flex justify-end gap-2 pt-2">
          <Skeleton height={36} width={80} rounded="lg" />
          <Skeleton height={36} width={80} rounded="lg" />
        </div>
      )}
    </div>
  );
};

interface SkeletonChatItemProps {
  className?: string;
}

/**
 * Skeleton for chat list item in sidebar
 */
export const SkeletonChatItem: FC<SkeletonChatItemProps> = ({ className = "" }) => {
  return (
    <div className={`flex items-center gap-3 px-3 py-2 ${className}`}>
      <div className="flex-1 space-y-1.5">
        <Skeleton height={14} width="85%" />
        <Skeleton height={10} width="50%" />
      </div>
    </div>
  );
};

interface SkeletonChatListProps {
  count?: number;
  className?: string;
}

/**
 * Skeleton for chat list in sidebar
 */
export const SkeletonChatList: FC<SkeletonChatListProps> = ({
  count = 6,
  className = "",
}) => {
  return (
    <div className={`space-y-1 ${className}`}>
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonChatItem key={i} />
      ))}
    </div>
  );
};

interface SkeletonIntegrationCardProps {
  className?: string;
}

/**
 * Skeleton for integration control card
 */
export const SkeletonIntegrationCard: FC<SkeletonIntegrationCardProps> = ({
  className = "",
}) => {
  return (
    <div className={`border border-gray-200 rounded-lg p-4 space-y-4 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Skeleton height={40} width={40} rounded="lg" />
          <div className="space-y-1">
            <Skeleton height={18} width={120} />
            <Skeleton height={12} width={80} />
          </div>
        </div>
        <Skeleton height={24} width={44} rounded="full" />
      </div>

      {/* Status section */}
      <div className="space-y-2 py-2 border-t border-gray-100">
        <Skeleton height={14} width={100} />
        <Skeleton height={12} width={150} />
      </div>

      {/* Config section */}
      <div className="space-y-3 pt-2 border-t border-gray-100">
        <Skeleton height={14} width={80} />
        <Skeleton height={36} width="100%" rounded="lg" />
        <Skeleton height={36} width="100%" rounded="lg" />
      </div>

      {/* Actions */}
      <div className="flex justify-end gap-2 pt-2">
        <Skeleton height={36} width={70} rounded="lg" />
        <Skeleton height={36} width={70} rounded="lg" />
      </div>
    </div>
  );
};

interface SkeletonButtonProps {
  className?: string;
  width?: number | string;
}

/**
 * Skeleton for button
 */
export const SkeletonButton: FC<SkeletonButtonProps> = ({
  className = "",
  width = 80,
}) => {
  return <Skeleton height={36} width={width} rounded="lg" className={className} />;
};

interface SkeletonSectionProps {
  className?: string;
  title?: boolean;
  rows?: number;
  hasButton?: boolean;
}

/**
 * Skeleton for settings section
 */
export const SkeletonSection: FC<SkeletonSectionProps> = ({
  className = "",
  title = true,
  rows = 3,
  hasButton = true,
}) => {
  return (
    <div className={`border border-gray-200 rounded-lg p-4 space-y-4 ${className}`}>
      {/* Section header */}
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          {title && <Skeleton height={18} width={180} />}
          <Skeleton height={12} width={250} />
        </div>
        {hasButton && <Skeleton height={36} width={70} rounded="lg" />}
      </div>
      {/* Content rows */}
      <div className="space-y-3">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex items-center justify-between">
            <Skeleton height={14} width={`${60 + (i * 10)}%`} className="max-w-[200px]" />
            <Skeleton height={24} width={44} rounded="full" />
          </div>
        ))}
      </div>
    </div>
  );
};

interface SkeletonFormFieldProps {
  className?: string;
  labelWidth?: number | string;
  inputHeight?: number;
  showLabel?: boolean;
}

/**
 * Skeleton for form field with label
 */
export const SkeletonFormField: FC<SkeletonFormFieldProps> = ({
  className = "",
  labelWidth = 120,
  inputHeight = 40,
  showLabel = true,
}) => {
  return (
    <div className={`space-y-2 ${className}`}>
      {showLabel && <Skeleton height={14} width={labelWidth} />}
      <Skeleton height={inputHeight} width="100%" rounded="lg" />
    </div>
  );
};

interface SkeletonMessageProps {
  className?: string;
  isUser?: boolean;
}

/**
 * Skeleton for chat message bubble
 */
export const SkeletonMessage: FC<SkeletonMessageProps> = ({
  className = "",
  isUser = false,
}) => {
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} ${className}`}>
      <div
        className={`rounded-2xl p-4 space-y-2 ${
          isUser ? "bg-blue-100 max-w-[70%]" : "bg-gray-100 max-w-[85%]"
        }`}
      >
        <Skeleton height={14} width={isUser ? 150 : 280} shimmer={false} className="bg-gray-200/60" />
        {!isUser && (
          <>
            <Skeleton height={14} width={320} shimmer={false} className="bg-gray-200/60" />
            <Skeleton height={14} width={200} shimmer={false} className="bg-gray-200/60" />
          </>
        )}
      </div>
    </div>
  );
};

interface SkeletonChatConversationProps {
  messages?: number;
  className?: string;
}

/**
 * Skeleton for full chat conversation
 */
export const SkeletonChatConversation: FC<SkeletonChatConversationProps> = ({
  messages = 3,
  className = "",
}) => {
  return (
    <div className={`space-y-4 ${className}`}>
      {Array.from({ length: messages }).map((_, i) => (
        <div key={i} className="space-y-3">
          <SkeletonMessage isUser />
          <SkeletonMessage />
        </div>
      ))}
    </div>
  );
};

interface SkeletonAiMlSettingsProps {
  className?: string;
}

/**
 * Skeleton for AI/ML settings page
 */
export const SkeletonAiMlSettings: FC<SkeletonAiMlSettingsProps> = ({ className = "" }) => {
  return (
    <div className={`space-y-8 ${className}`}>
      {/* Model & Generation section */}
      <div className="border border-gray-200 rounded-lg p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <Skeleton height={18} width={160} />
            <Skeleton height={12} width={280} />
          </div>
          <Skeleton height={36} width={70} rounded="lg" />
        </div>
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <div className="space-y-3">
            <Skeleton height={14} width={100} />
            <Skeleton height={42} width="100%" rounded="lg" />
          </div>
          <div className="flex items-center gap-3 mt-4">
            <Skeleton height={14} width={90} />
            <Skeleton height={40} width={80} rounded="lg" />
          </div>
        </div>
      </div>

      {/* Safety & Observability section */}
      <div className="border border-gray-200 rounded-lg p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <Skeleton height={18} width={180} />
            <Skeleton height={12} width={260} />
          </div>
          <Skeleton height={36} width={70} rounded="lg" />
        </div>
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <Skeleton height={14} width={120} />
            <Skeleton height={14} width={80} />
          </div>
          <div className="flex gap-2">
            <Skeleton height={40} width="100%" rounded="lg" />
            <Skeleton height={40} width={100} rounded="lg" />
          </div>
        </div>
        <div className="flex items-center gap-3 mt-2">
          <Skeleton height={14} width={160} />
          <Skeleton height={24} width={44} rounded="full" />
        </div>
      </div>
    </div>
  );
};

interface SkeletonUserManagementProps {
  className?: string;
}

/**
 * Skeleton for User Management page
 */
export const SkeletonUserManagement: FC<SkeletonUserManagementProps> = ({ className = "" }) => {
  return (
    <div className={`space-y-6 ${className}`}>
      {/* Auth methods section */}
      <SkeletonSection rows={4} />

      {/* Search and count */}
      <div className="flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between">
        <Skeleton height={40} width={280} rounded="lg" />
        <Skeleton height={14} width={60} />
      </div>

      {/* Table */}
      <SkeletonTable rows={5} columns={3} />
    </div>
  );
};

interface SkeletonAuditProps {
  className?: string;
}

/**
 * Skeleton for Audit page
 */
export const SkeletonAudit: FC<SkeletonAuditProps> = ({ className = "" }) => {
  return (
    <div className={`space-y-6 ${className}`}>
      {/* Settings History section */}
      <div className="border border-gray-200 rounded-lg p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <Skeleton height={18} width={140} />
            <Skeleton height={12} width={200} />
          </div>
          <Skeleton height={36} width={80} rounded="lg" />
        </div>
        <SkeletonTable rows={6} columns={7} />
      </div>

      {/* Legend section */}
      <div className="border border-gray-200 rounded-lg p-4 space-y-4">
        <Skeleton height={16} width={60} />
        <Skeleton height={12} width={180} />
        <div className="flex flex-wrap gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} height={14} width={80} />
          ))}
        </div>
      </div>
    </div>
  );
};

interface SkeletonIntegrationsProps {
  count?: number;
  className?: string;
}

/**
 * Skeleton for Integrations page
 */
export const SkeletonIntegrations: FC<SkeletonIntegrationsProps> = ({
  count = 2,
  className = "",
}) => {
  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header with add button */}
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-1">
          <Skeleton height={14} width={280} />
        </div>
        <Skeleton height={32} width={60} rounded="lg" />
      </div>

      {/* Integration cards */}
      <div className="flex flex-col gap-3">
        {Array.from({ length: count }).map((_, i) => (
          <SkeletonIntegrationCard key={i} />
        ))}
      </div>
    </div>
  );
};

export default Skeleton;

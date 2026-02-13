interface StopIconProps {
  className?: string;
  size?: number;
}

const StopIcon = ({ className = "", size = 20 }: StopIconProps) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="currentColor"
    className={className}
  >
    <rect x="6" y="6" width="12" height="12" rx="2" />
  </svg>
);

export default StopIcon;

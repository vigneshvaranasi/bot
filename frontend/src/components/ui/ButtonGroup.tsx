interface ButtonGroupProps {
  children: React.ReactNode;
  className?: string;
};

const ButtonGroup: React.FC<ButtonGroupProps> = ({
  children,
  className = "",
}) => {
  return (
    <div
      className={`inline-flex items-center bg-white rounded-full p-1 shadow-md ${className}`}
    >
      {children}
    </div>
  );
};

export default ButtonGroup;

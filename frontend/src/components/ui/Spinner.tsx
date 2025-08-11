import React, { type FC } from "react";

export interface SpinnerProps {
  size?: number;
  color?: string;
  bars?: number;
  duration?: number;
}

const Spinner: FC<SpinnerProps> = ({
  size = 24,
  color = "#000",
  bars = 9,
  duration = 1.2,
}) => {
  const s = Math.max(size, 12);
  const barWidth = s * 0.12
  const barHeight = s * 0.34;
  const arr = Array.from({ length: bars });

  return (
    <div
      className="relative inline-block"
      role="status"
      aria-label="Loading"
      style={{ width: s, height: s }}
    >
      {arr.map((_, i) => {
        const rotation = (360 / bars) * i;
        const delay = (-duration + (duration / bars) * i).toFixed(3) + "s";
        return (
          <div
            key={i}
            className="absolute inset-0 flex items-center justify-center"
            style={{ transform: `rotate(${rotation}deg)` }}
          >
            <div
              style={{
                width: barWidth,
                height: barHeight,
                backgroundColor: color,
                borderRadius: s,
                animation: `spinner-fade ${duration}s linear infinite`,
                animationDelay: delay,
                transform: `translateY(-${s / 2 - barHeight / 2}px)`,
                opacity: 0,
              }}
            />
          </div>
        );
      })}
    </div>
  );
};

export default Spinner;

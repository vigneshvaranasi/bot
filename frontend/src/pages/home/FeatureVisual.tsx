import { FONT_DISPLAY, FONT_MONO } from "./tokens";

export type Visual =
  | { type: "tools"; items: readonly { symbol: string; label: string }[] }
  | { type: "flow"; items: readonly { label: string; score: string; highlight?: boolean }[] }
  | { type: "chips"; items: readonly { label: string; tone?: string }[] };

const FeatureVisual = ({ visual, variant }: { visual: Visual; variant: string }) => {
  const dark = variant === "dark";

  if (visual.type === "tools") {
    return (
      <div className="flex flex-col gap-2 sm:grid sm:grid-cols-5">
        {visual.items.map((t) => (
          <div
            key={t.label}
            className={[
              "rounded-[10px] border flex items-center gap-3 px-3 py-2.5",
              "sm:flex-col sm:items-stretch sm:text-center sm:gap-0 sm:py-3.5 sm:px-2.5",
              FONT_MONO,
              "text-[12px] sm:text-[11px]",
              dark
                ? "bg-white/5 border-white/10 text-white/65"
                : "bg-black/[0.04] border-black/5 text-black/60",
            ].join(" ")}
          >
            <strong
              className={[
                FONT_DISPLAY,
                "text-lg font-medium tracking-[-0.01em] flex-none w-6 sm:w-auto sm:block sm:mb-1",
                dark ? "text-[#f5f5f0]" : "text-[#0a0a0a]",
              ].join(" ")}
            >
              {t.symbol}
            </strong>
            <span className="flex-1 sm:block">{t.label}</span>
          </div>
        ))}
      </div>
    );
  }

  if (visual.type === "flow") {
    return (
      <div className={`flex flex-col gap-1.5 ${FONT_MONO} text-xs`}>
        {visual.items.map((r) => {
          const cls = r.highlight
            ? "bg-[#ef6101] text-white border-[#ef6101]"
            : dark
              ? "bg-white/5 border-white/10"
              : "bg-black/[0.04] border-black/5";
          const scoreCls = r.highlight ? "text-white/75" : dark ? "text-white/50" : "text-black/40";
          return (
            <div
              key={r.label}
              className={`px-3.5 py-2.5 rounded-[10px] flex justify-between items-center border ${cls}`}
            >
              <span>{r.label}</span>
              <span className={`text-[11px] ${scoreCls}`}>{r.score}</span>
            </div>
          );
        })}
      </div>
    );
  }

  if (visual.type === "chips") {
    return (
      <div className={`flex gap-2 ${FONT_MONO} text-xs ${dark ? "text-white/60" : "text-black/60"}`}>
        {visual.items.map((c) => {
          const isPos = c.tone === "pos";
          return (
            <span
              key={c.label}
              className={[
                "px-3 py-1.5 rounded-full border",
                isPos
                  ? "bg-[#0c861c]/20 border-[#0c861c]/40 text-[#0c861c]"
                  : dark
                    ? "bg-white/5 border-white/10"
                    : "bg-black/5 border-black/10",
              ].join(" ")}
            >
              {c.label}
            </span>
          );
        })}
      </div>
    );
  }

  return null;
};

export default FeatureVisual;
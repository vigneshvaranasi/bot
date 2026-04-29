import landing from "../../config/homeConfig";
import { EYEBROW_LIGHT, FONT_DISPLAY, FONT_MONO, HEAD_XL, WRAP } from "./tokens";
import Reveal from "./Reveal";
import FeatureVisual from "./FeatureVisual";

const SPAN: Record<number, string> = {
  4: "lg:col-span-4",
  5: "lg:col-span-5",
  6: "lg:col-span-6",
  7: "lg:col-span-7",
  8: "lg:col-span-8",
  12: "lg:col-span-12",
};

const Features = () => {
  const { features } = landing;

  return (
    <section
      id="features"
      data-paper="true"
      className="bg-[#f5f5f0] text-[#0a0a0a] py-[clamp(80px,12vw,180px)]"
    >
      <div className={WRAP}>
        <Reveal>
          <div className="max-w-[740px] mb-12 sm:mb-16 lg:mb-20">
            <div className={EYEBROW_LIGHT}>{features.eyebrow}</div>
            <h2 className={`${HEAD_XL} mt-4`}>{features.title}</h2>
          </div>
        </Reveal>

        <div className="grid grid-cols-12 gap-4 sm:gap-6">
          {features.items.map((f) => {
            const variantBg =
              f.variant === "dark"
                ? "bg-[#0a0a0a] text-[#f5f5f0] border-[#0a0a0a]"
                : f.variant === "accent"
                  ? "bg-[#fff5ed] text-[#0a0a0a] border-[#ef6101]/25"
                  : "bg-white border-black/5";
            const numTone =
              f.variant === "dark"
                ? "text-white/50"
                : f.variant === "accent"
                  ? "text-[#ef6101]"
                  : "text-black/40";
            const bodyTone =
              f.variant === "dark"
                ? "text-white/65"
                : f.variant === "accent"
                  ? "text-black/65"
                  : "text-black/60";
            const span = `col-span-12 ${SPAN[f.span] ?? "md:col-span-12"}`;
            const isTall = "size" in f && f.size === "tall";
            const minH = isTall ? "min-h-[420px] lg:min-h-[520px]" : "min-h-[340px] lg:min-h-[420px]";

            return (
              <Reveal key={f.id} className={span}>
                <article
                  className={[
                    "group relative isolate overflow-hidden rounded-[20px] sm:rounded-[28px] p-6 sm:p-8 flex flex-col gap-4 sm:gap-5 border h-full",
                    variantBg,
                    minH,
                    "transition-transform duration-[400ms] ease-[cubic-bezier(0.2,0.7,0.2,1)] hover:-translate-y-1",
                  ].join(" ")}
                >
                  {f.variant === "accent" && (
                    <span
                      aria-hidden
                      className="pointer-events-none absolute -top-24 -right-20 w-[280px] h-[280px] rounded-full bg-[radial-gradient(circle,rgba(239,97,1,0.28),transparent_70%)] blur-[30px] -z-10"
                    />
                  )}
                  <div className={`${FONT_MONO} text-[11px] tracking-[0.08em] ${numTone}`}>{f.num}</div>
                  <h3
                    className={`${FONT_DISPLAY} text-[clamp(22px,2.2vw,30px)] font-medium tracking-[-0.02em] leading-[1.1] m-0 [text-wrap:balance]`}
                  >
                    {f.title}
                  </h3>
                  <p className={`text-[14.5px] leading-[1.5] max-w-[42ch] ${bodyTone}`}>{f.body}</p>
                  {"visual" in f && f.visual && (
                    <div className="mt-auto pt-5">
                      <FeatureVisual visual={f.visual} variant={f.variant} />
                    </div>
                  )}
                </article>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
};

export default Features;
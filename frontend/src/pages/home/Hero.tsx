import { useEffect, useState } from "react";
import landing from "../../config/homeConfig";
import { FONT_DISPLAY, FONT_MONO, HEAD_DISPLAY, LEDE_LIGHT, WRAP } from "./tokens";
import Reveal from "./Reveal";

const Hero = () => {
  const { hero } = landing;
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => { if (window.scrollY > 40) setScrolled(true); };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <section
      id="hero"
      data-paper="true"
      className="relative min-h-[100svh] sm:min-h-0 pt-[120px] sm:pt-[140px] lg:pt-[160px] pb-[100px] sm:pb-[120px] lg:pb-[140px] overflow-hidden bg-[#f5f5f0] text-[#0a0a0a] flex flex-col"
    >
      <div className={`${WRAP} flex-1 flex flex-col justify-center sm:block`}>
        <div className="max-w-[920px] mx-auto text-center">
          <Reveal>
            <div className="inline-flex items-center gap-2.5 py-[7px] pl-[7px] pr-3.5 rounded-full border border-black/10 bg-black/[0.04] text-[13px] text-black/60 mb-7">
              <span className="w-[22px] h-[22px] rounded-full bg-[#0a0a0a] grid place-items-center text-[#f5f5f0] text-[11px]">
                ✦
              </span>
              <span>{hero.badge}</span>
            </div>
          </Reveal>
          <Reveal delay={40}>
            <h1 className={`${HEAD_DISPLAY} mb-7`}>
              {hero.title.map((line, i) => (
                <span key={i} className="block">
                  {line}
                </span>
              ))}
            </h1>
          </Reveal>
          <Reveal delay={80}>
            <p className={`${LEDE_LIGHT} mx-auto`}>{hero.lede}</p>
          </Reveal>
          <Reveal delay={120}>
            <div className="mt-10 flex justify-center">
              <a
                href="/auth"
                className="inline-flex items-center gap-2 px-6 py-3 rounded-full bg-[#0a0a0a] text-[#f5f5f0] text-[14px] font-medium tracking-[-0.01em] hover:opacity-80 transition-opacity"
              >
                Get started
              </a>
            </div>
          </Reveal>
          <Reveal delay={160}>
            <div className="grid grid-cols-3 sm:flex sm:flex-wrap sm:gap-x-10 sm:justify-center gap-y-6 mt-10 pt-8 border-t border-black/10">
              {hero.metrics.map((m) => (
                <div key={m.label} className="text-center sm:text-left">
                  <small
                    className={`block ${FONT_MONO} text-[10px] sm:text-[11px] tracking-[0.06em] uppercase text-black/40 mb-1.5`}
                  >
                    {m.label}
                  </small>
                  <strong className={`${FONT_DISPLAY} text-[clamp(13px,3.8vw,22px)] sm:text-[22px] font-medium tracking-[-0.01em] whitespace-nowrap`}>
                    {m.value}
                  </strong>
                </div>
              ))}
            </div>
          </Reveal>
        </div>
      </div>

      <div
        className={`absolute bottom-8 left-0 right-0 flex flex-col items-center gap-1.5 transition-opacity duration-500 sm:hidden ${scrolled ? "opacity-0 pointer-events-none" : "opacity-100"}`}
      >
        <span className={`${FONT_MONO} text-[10px] tracking-[0.08em] uppercase text-black/30`}>
          scroll to explore
        </span>
        <svg
          className="animate-bounce text-black/30"
          width="16" height="16" viewBox="0 0 16 16" fill="none"
        >
          <path d="M8 3v10M3.5 8.5l4.5 4.5 4.5-4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    </section>
  );
};

export default Hero;
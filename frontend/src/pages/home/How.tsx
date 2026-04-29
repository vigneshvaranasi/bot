import landing from "../../config/homeConfig";
import { EYEBROW_DARK, FONT_DISPLAY, FONT_MONO, HEAD_XL, LEDE_DARK, WRAP } from "./tokens";
import Reveal from "./Reveal";

const How = () => {
  const { how } = landing;
  return (
    <section id="how" className="bg-[#0a0a0a] py-[clamp(80px,12vw,180px)]">
      <div className={WRAP}>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 lg:gap-10 mb-12 sm:mb-16 lg:mb-20 items-end">
          <Reveal>
            <div className={EYEBROW_DARK}>{how.eyebrow}</div>
            <h2 className={`${HEAD_XL} mt-4`}>{how.title}</h2>
          </Reveal>
          <Reveal delay={80}>
            <p className={`${LEDE_DARK} lg:justify-self-end max-w-[36ch]`}>{how.lede}</p>
          </Reveal>
        </div>
        <Reveal>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-px bg-white/10 border-y border-white/10">
            {how.steps.map((s) => (
              <div key={s.num} className="bg-[#0a0a0a] p-6 sm:p-8 lg:p-9 lg:px-7 lg:min-h-[340px] flex flex-col gap-3">
                <div className={`${FONT_MONO} text-xs text-[#ef6101] mb-auto`}>// {s.num}</div>
                <h3
                  className={`${FONT_DISPLAY} text-[22px] font-medium tracking-[-0.015em] leading-[1.2] mt-0 mb-3`}
                >
                  {s.title}
                </h3>
                <p className="text-white/60 text-sm leading-[1.5]">{s.body}</p>
              </div>
            ))}
          </div>
        </Reveal>
      </div>
    </section>
  );
};

export default How;
import landing from "../../config/homeConfig";
import { EYEBROW_DARK, FONT_DISPLAY, FONT_MONO, HEAD_XL, LEDE_DARK, WRAP } from "./tokens";
import Reveal from "./Reveal";
import { IntegrationLogo } from "./logos";

const Integrations = () => {
  const { integrations } = landing;

  return (
    <section
      id="integrations"
      className="bg-[#0a0a0a] py-[clamp(80px,12vw,180px)] border-t border-white/10"
    >
      <div className={WRAP}>
        <Reveal>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 lg:gap-10 items-end mb-12 sm:mb-16 lg:mb-[72px]">
            <div>
              <div className={EYEBROW_DARK}>{integrations.eyebrow}</div>
              <h2 className={`${HEAD_XL} mt-4`}>{integrations.title}</h2>
            </div>
            <p className={`${LEDE_DARK} lg:justify-self-end max-w-[36ch]`}>
              {integrations.lede}
            </p>
          </div>
        </Reveal>

        <Reveal>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-px bg-white/10 border-y border-white/10">
            {integrations.cards.map((c, i) => (
              <article
                key={c.id}
                className="bg-[#0a0a0a] p-7 sm:p-10 md:p-12 min-h-[320px] md:min-h-[400px] flex flex-col group"
              >
                <span className={`${FONT_MONO} text-[12px] text-[#ef6101]`}>// 0{i + 1}</span>

                <div className="mt-10 sm:mt-14 mb-auto">
                  <div className="w-[56px] h-[56px] sm:w-[64px] sm:h-[64px] transition-transform duration-500 ease-[cubic-bezier(0.2,0.7,0.2,1)] group-hover:translate-y-[-2px]">
                    <IntegrationLogo id={c.id} />
                  </div>
                </div>

                <h3
                  className={`${FONT_DISPLAY} text-[clamp(30px,5vw,56px)] font-medium tracking-[-0.03em] leading-[1] m-0 mt-10 sm:mt-12`}
                >
                  {c.name}.
                </h3>
                <p className="mt-4 m-0 text-[15px] leading-[1.55] text-white/65 max-w-[44ch]">
                  {c.desc}
                </p>
              </article>
            ))}
          </div>
        </Reveal>
      </div>
    </section>
  );
};

export default Integrations;
import landing from "../../config/homeConfig";
import { EYEBROW_LIGHT, FONT_DISPLAY, FONT_MONO, HEAD_XL, LEDE_LIGHT, WRAP } from "./tokens";
import Reveal from "./Reveal";

const Problem = () => {
  const { problem } = landing;
  return (
    <section data-paper="true" className="bg-[#f5f5f0] text-[#0a0a0a] py-[clamp(80px,12vw,180px)]">
      <div className={WRAP}>
        <Reveal>
          <div className="max-w-[900px] mb-12 sm:mb-16 lg:mb-[72px]">
            <div className={EYEBROW_LIGHT}>{problem.eyebrow}</div>
            <h2 className={`${HEAD_XL} my-4`}>{problem.title}</h2>
            <p className={LEDE_LIGHT}>{problem.lede}</p>
          </div>
        </Reveal>
        <Reveal>
          <ul className="list-none p-0 m-0 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-px bg-black/10 border border-black/10 rounded-[18px] overflow-hidden">
            {problem.items.map((it) => (
              <li key={it.num} className="bg-[#f5f5f0] p-6 sm:p-8 sm:px-7 flex flex-col gap-3 min-h-[160px] sm:min-h-[180px]">
                <div className={`${FONT_MONO} text-xs text-black/40`}>{it.num}</div>
                <div
                  className={`${FONT_DISPLAY} text-[22px] font-medium tracking-[-0.015em] leading-[1.2] mt-auto`}
                >
                  {it.title}
                </div>
              </li>
            ))}
          </ul>
        </Reveal>
      </div>
    </section>
  );
};

export default Problem;
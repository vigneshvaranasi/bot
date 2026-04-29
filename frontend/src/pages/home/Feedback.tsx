import { Fragment } from "react";
import landing from "../../config/homeConfig";
import { EYEBROW_DARK, FONT_DISPLAY, HEAD_XL, LEDE_DARK, WRAP } from "./tokens";
import Reveal from "./Reveal";

const LABEL_POS: Record<string, string> = {
  top: "top-0 left-1/2 -translate-x-1/2 -translate-y-1/2",
  right: "top-1/2 right-0 translate-x-1/2 -translate-y-1/2",
  bottom: "bottom-0 left-1/2 -translate-x-1/2 translate-y-1/2",
  left: "top-1/2 left-0 -translate-x-1/2 -translate-y-1/2",
};

const SUB_POS: Record<string, string> = {
  top: "bottom-full mb-8 sm:mb-10 left-1/2 -translate-x-1/2 text-center w-[120px] sm:w-[140px]",
  right: "top-1/2 right-0 translate-x-1/2 mt-7 sm:mt-9 text-center w-[100px] sm:w-[120px]",
  bottom: "top-full mt-8 sm:mt-10 left-1/2 -translate-x-1/2 text-center w-[120px] sm:w-[140px]",
  left: "top-1/2 left-0 -translate-x-1/2 mt-7 sm:mt-9 text-center w-[100px] sm:w-[120px]",
};

const Feedback = () => {
  const { feedback } = landing;
  return (
    <section className="bg-[#0a0a0a] border-t border-white/10">
      <div className={`${WRAP} py-[clamp(80px,12vw,180px)]`}>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-[clamp(40px,6vw,80px)] items-center">
          <Reveal>
            <div>
              <div className={EYEBROW_DARK}>{feedback.eyebrow}</div>
              <h2 className={`${HEAD_XL} mt-4 mb-6`}>{feedback.title}</h2>
              <p className={LEDE_DARK}>{feedback.lede}</p>
            </div>
          </Reveal>

          <Reveal scale>
            <div className="flex justify-center items-center py-12 sm:py-16">
              <div className="relative isolate w-[280px] h-[280px] sm:w-[340px] sm:h-[340px] lg:w-[380px] lg:h-[380px] rounded-full border border-dashed border-white/15" style={{ isolation: "isolate" }}>
                <span aria-hidden className="landing-orbit absolute top-0 left-1/2 w-0 h-0 block z-[-1]">
                  <span className="absolute -translate-x-1/2 -translate-y-1/2 text-lg text-[#ef6101] leading-none">
                    →
                  </span>
                </span>

                {feedback.loop.map((n) => (
                  <Fragment key={n.position}>
                    <span
                      className={[
                        "absolute z-[50] whitespace-nowrap",
                        LABEL_POS[n.position],
                        FONT_DISPLAY,
                        "text-sm sm:text-lg font-medium tracking-[-0.01em]",
                        "bg-[#0a0a0a] px-3 sm:px-[18px] py-1 sm:py-1.5 rounded-full border border-white/15",
                      ].join(" ")}
                    >
                      {n.label}
                    </span>
                    <span
                      className={[
                        "absolute z-[60] text-[11px] sm:text-xs text-white/45 leading-[1.3]",
                        SUB_POS[n.position],
                      ].join(" ")}
                    >
                      {n.sub}
                    </span>
                  </Fragment>
                ))}
              </div>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
};

export default Feedback;
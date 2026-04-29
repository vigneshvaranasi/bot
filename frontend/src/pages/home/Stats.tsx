import landing from "../../config/homeConfig";
import { FONT_DISPLAY, WRAP } from "./tokens";
import Reveal from "./Reveal";

const Stats = () => {
  const { stats } = landing;
  return (
    <section className="py-[clamp(56px,7vw,96px)]">
      <div className={WRAP}>
        <Reveal>
          <div className="grid grid-cols-2 md:grid-cols-4 border-y border-white/10">
            {stats.map((s, i) => {
              const onPhone2x2 = i % 2 === 0;
              const onPhoneTopRow = i < 2;
              return (
                <div
                  key={i}
                  className={[
                    "p-7 sm:p-10",
                    onPhone2x2 ? "border-r border-white/10" : "",
                    i < stats.length - 1 ? "md:border-r md:border-white/10" : "md:border-r-0",
                    onPhoneTopRow ? "border-b border-white/10 md:border-b-0" : "",
                  ].join(" ")}
                >
                  <div
                    className={`${FONT_DISPLAY} font-medium tracking-[-0.035em] leading-none text-[clamp(36px,5vw,64px)]`}
                  >
                    {s.big}
                    <span className="text-[#ef6101] text-[0.6em] ml-0.5">{s.unit}</span>
                  </div>
                  <small className="block mt-3 text-white/60 text-[13px] sm:text-sm max-w-[24ch] leading-[1.4]">
                    {s.caption}
                  </small>
                </div>
              );
            })}
          </div>
        </Reveal>
      </div>
    </section>
  );
};

export default Stats;
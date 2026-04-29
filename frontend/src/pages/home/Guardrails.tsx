import landing from "../../config/homeConfig";
import { EYEBROW_LIGHT, FONT_DISPLAY, FONT_MONO, HEAD_XL, LEDE_LIGHT, WRAP } from "./tokens";
import Reveal from "./Reveal";

const Guardrails = () => {
  const { guardrails } = landing;

  return (
    <section id="guardrails" data-paper="true" className="bg-[#ececE4] text-[#0a0a0a]">
      <div className={`${WRAP} py-[clamp(80px,12vw,180px)]`}>
        <Reveal>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 lg:gap-10 items-end mb-12 sm:mb-16 lg:mb-[72px]">
            <div>
              <div className={EYEBROW_LIGHT}>{guardrails.eyebrow}</div>
              <h2 className={`${HEAD_XL} mt-4`}>{guardrails.title}</h2>
            </div>
            <p className={`${LEDE_LIGHT} lg:justify-self-end max-w-[38ch]`}>{guardrails.lede}</p>
          </div>
        </Reveal>

        <Reveal>
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-px bg-black/10 border border-black/10 rounded-[18px] overflow-hidden">
            {guardrails.pipeline.map((p, i) => {
              const isGate = p.kind === "gate";
              const outcome = (p as { outcome?: "allow" | "block" }).outcome;

              return (
                <div
                  key={i}
                  className={[
                    "relative p-5 sm:p-6 lg:p-7 flex flex-col gap-2 lg:gap-3 lg:min-h-[260px]",
                    isGate ? "bg-[#0a0a0a] text-[#f5f5f0]" : "bg-[#ececE4]",
                  ].join(" ")}
                >
                  {outcome && (
                    <span
                      aria-hidden
                      className={[
                        "absolute top-0 left-0 right-0 h-[3px]",
                        outcome === "allow" ? "bg-[#0c861c]" : "bg-[#e04040]",
                      ].join(" ")}
                    />
                  )}

                  <span
                    className={[
                      FONT_MONO,
                      "text-[11px] tracking-[0.04em]",
                      isGate ? "text-white/45" : "text-black/40",
                    ].join(" ")}
                  >
                    {p.num}
                  </span>

                  {outcome && (
                    <span
                      className={[
                        "inline-flex items-center gap-1.5 w-fit px-2 py-[3px] rounded-full",
                        FONT_MONO,
                        "text-[10px] uppercase tracking-[0.06em]",
                        outcome === "allow"
                          ? "bg-[#0c861c]/15 text-[#0c861c] border border-[#0c861c]/40"
                          : "bg-[#e04040]/10 text-[#a02828] border border-[#e04040]/30",
                      ].join(" ")}
                    >
                      <span
                        className={[
                          "w-1.5 h-1.5 rounded-full",
                          outcome === "allow" ? "bg-[#0c861c]" : "bg-[#e04040]",
                        ].join(" ")}
                      />
                      {outcome === "allow" ? "Allow" : "Block"}
                    </span>
                  )}

                  <h3
                    className={[
                      FONT_DISPLAY,
                      "text-[20px] font-medium tracking-[-0.015em] leading-[1.2] m-0 mt-2 lg:mt-auto",
                      isGate ? "text-[#f5f5f0]" : "text-[#0a0a0a]",
                    ].join(" ")}
                  >
                    {p.title}
                  </h3>
                  <p
                    className={[
                      "m-0 text-[13.5px] leading-[1.45]",
                      isGate ? "text-white/65" : "text-black/60",
                    ].join(" ")}
                  >
                    {p.body}
                  </p>
                </div>
              );
            })}
          </div>
        </Reveal>
      </div>
    </section>
  );
};

export default Guardrails;

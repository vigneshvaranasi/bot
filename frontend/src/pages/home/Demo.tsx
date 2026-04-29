import { useMemo, useState } from "react";
import landing from "../../config/homeConfig";
import { EYEBROW_DARK, FONT_MONO, HEAD_XL, WRAP } from "./tokens";
import Reveal from "./Reveal";
import Bubble from "../../components/ui/Bubble";
import { ChatAction } from "../../components/ui/ChatAction";
import InputBox from "../../components/ui/InputBox";
import SendIcon from "../../components/icons/SendIcon";

type Tab = (typeof landing.demo.tabs)[number];
type Exchange = Tab["exchanges"][number];

const TIME_FMT = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
  hour: "numeric",
  minute: "2-digit",
  hour12: true,
});

const Demo = () => {
  const { demo } = landing;
  const tabs = demo.tabs;
  const [activeId, setActiveId] = useState<Tab["id"]>(tabs[0].id);
  const [input, setInput] = useState("");
  const active = useMemo(() => tabs.find((t) => t.id === activeId) ?? tabs[0], [activeId, tabs]);
  const now = TIME_FMT.format(new Date());

  return (
    <section
      id="demo"
      className="bg-[#0a0a0a] py-[clamp(80px,12vw,160px)] border-t border-white/10"
    >
      <div className={WRAP}>
        <Reveal>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 lg:gap-10 items-end mb-12 sm:mb-16 lg:mb-[72px]">
            <div>
              <div className={EYEBROW_DARK}>{demo.eyebrow}</div>
              <h2 className={`${HEAD_XL} mt-4`}>{demo.title}</h2>
            </div>
          </div>
        </Reveal>

        <Reveal scale>
          <div
            className="dark max-w-[960px] mx-auto rounded-[16px] sm:rounded-[20px] border overflow-hidden shadow-[0_60px_120px_-30px_rgba(0,0,0,0.7)]"
            style={{
              background: "var(--color-surface-primary)",
              borderColor: "var(--color-border-default)",
              color: "var(--color-text-primary)",
            }}
          >
            <div
              className="flex gap-1.5 px-4 sm:px-6 pt-4 sm:pt-5 pb-3 border-b overflow-x-auto whitespace-nowrap [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
              style={{ borderColor: "var(--color-border-subtle)" }}
            >
              {tabs.map((t) => {
                const isActive = t.id === activeId;
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setActiveId(t.id)}
                    className={[
                      "flex-none px-3 sm:px-3.5 py-1.5 rounded-full border text-[12px] sm:text-[12.5px] tracking-[0.02em] cursor-pointer",
                      FONT_MONO,
                      "transition-colors",
                      isActive
                        ? "bg-[#ef6101] border-[#ef6101] text-white"
                        : "bg-surface-tertiary border-border-default text-text-secondary hover:text-text-primary",
                    ].join(" ")}
                  >
                    {t.label}
                  </button>
                );
              })}
            </div>

            <div
              key={active.id}
              className="px-4 sm:px-6 py-5 sm:py-6 flex flex-col landing-fade-in min-h-[400px] sm:min-h-[460px]"
            >
              {active.exchanges.map((ex, i) => (
                <DemoExchange key={i} exchange={ex} time={now} />
              ))}
            </div>

            <div className="w-full px-4 pb-5">
              <div className="flex items-end gap-x-2 mx-auto">
                <InputBox
                  className="flex-1"
                  variant="multiline"
                  backgroundColor="surface-secondary"
                  value={input}
                  onChange={setInput}
                  placeholder={demo.placeholder}
                  rows={1}
                  maxHeight={140}
                />
                <button
                  type="button"
                  aria-label="Send"
                  disabled={!input.trim()}
                  className={[
                    "flex-none h-10 w-10 rounded-xl mb-1.5 flex items-center justify-center transition-colors",
                    input.trim()
                      ? "bg-accent hover:bg-accent-hover text-text-inverse cursor-pointer"
                      : "bg-surface-tertiary text-text-tertiary cursor-not-allowed",
                  ].join(" ")}
                >
                  <SendIcon size={18} />
                </button>
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
};

const DemoExchange = ({ exchange, time }: { exchange: Exchange; time: string }) => {
  return (
    <div>
      <div>
        <Bubble variant="user" content={exchange.user} />
        <p className="text-xs text-text-tertiary mt-0.5 mr-1 text-right">{time}</p>
      </div>

      <div>
        <Bubble variant="bot" content={exchange.bot} />
        <p className="text-xs text-text-tertiary mt-0.5">{time}</p>
      </div>

      <div className="flex items-center gap-1 ml-[-7px] mt-1 pb-1 mb-4">
        <ChatAction type="thumbsUp" />
        <ChatAction type="thumbsDown" />
        <ChatAction type="copy" content={exchange.bot} />
        <ChatAction type="speaker" content={exchange.bot} />
        <ChatAction
          type="metrics"
          responseMetrics={{
            timeToFirstToken: exchange.ttft,
            totalResponseTime: exchange.rt,
            providerType: exchange.provider,
            modelId: exchange.model,
          }}
        />
      </div>
    </div>
  );
};

export default Demo;
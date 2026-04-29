import landing from "../../config/homeConfig";
import { FONT_MONO, WRAP } from "./tokens";

const Footer = () => {
  const { footer } = landing;
  return (
    <footer className="bg-[#0a0a0a] border-t border-white/10 py-8">
      <div className={WRAP}>
        <div
          className={`flex flex-col items-center gap-2 sm:flex-row sm:justify-between sm:gap-3 ${FONT_MONO} text-[11px] text-white/40 tracking-[0.05em] uppercase`}
        >
          <span>{footer.bottomLeft}</span>
          <span>{footer.bottomCenter}</span>
          <span>{footer.bottomRight}</span>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
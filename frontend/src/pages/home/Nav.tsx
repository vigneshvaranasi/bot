import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import landing from "../../config/homeConfig";

const Nav = () => {
  const { nav } = landing;
  const [onPaper, setOnPaper] = useState(true);

  useEffect(() => {
    const onScroll = () => {
      const navY = 40;
      const sections = document.querySelectorAll<HTMLElement>("[data-paper='true']");
      let hit = false;
      sections.forEach((sec) => {
        const r = sec.getBoundingClientRect();
        if (r.top <= navY && r.bottom > navY) hit = true;
      });
      setOnPaper(hit);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <nav
      className={[
        "fixed top-3.5 z-50 flex items-center gap-1.5 md:gap-3 py-2 pr-2 pl-5 md:pl-7 md:pr-3 rounded-full border text-sm",
        "left-3 right-3 justify-between",
        "md:left-1/2 md:right-auto md:-translate-x-1/2 md:justify-between md:min-w-[340px] lg:min-w-[440px]",
        "[backdrop-filter:blur(16px)_saturate(150%)] [-webkit-backdrop-filter:blur(16px)_saturate(150%)]",
        "transition-[background,border-color,color] duration-[400ms] ease-[cubic-bezier(0.2,0.7,0.2,1)]",
        onPaper
          ? "bg-[#f5f5f0]/80 border-black/10 text-black"
          : "bg-[#141414]/70 border-white/10 text-[#f5f5f0]",
      ].join(" ")}
    >
      <div className="whitespace-nowrap font-semibold tracking-[-0.01em]">
        <span>{nav.brand}</span>
      </div>

      <Link
        to={nav.signIn.href}
        className={[
          "inline-flex items-center gap-2 py-[7px] px-4 rounded-full text-[13px] font-medium border",
          "transition-[transform,background,color,border-color] duration-200 ease-[cubic-bezier(0.2,0.7,0.2,1)]",
          onPaper
            ? "text-[#f5f5f0] bg-[#0a0a0a] border-[#0a0a0a] hover:bg-[#222]"
            : "text-[#0a0a0a] bg-[#f5f5f0] border-[#f5f5f0] hover:bg-white",
        ].join(" ")}
      >
        {nav.signIn.label}
      </Link>
    </nav>
  );
};

export default Nav;
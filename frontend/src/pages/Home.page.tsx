import { useEffect } from "react";
import Nav from "./home/Nav";
import Hero from "./home/Hero";
import Stats from "./home/Stats";
import Problem from "./home/Problem";
import How from "./home/How";
import Guardrails from "./home/Guardrails";
import Integrations from "./home/Integrations";
import Features from "./home/Features";
import Feedback from "./home/Feedback";
import Demo from "./home/Demo";
import Footer from "./home/Footer";

const HomePage = () => {
  useEffect(() => {
    const html = document.documentElement;
    const body = document.body;
    const root = document.getElementById("root");
    const prev = {
      htmlHeight: html.style.height,
      bodyHeight: body.style.height,
      bodyBg: body.style.backgroundColor,
      rootHeight: root?.style.height ?? "",
    };
    html.style.height = "auto";
    body.style.height = "auto";
    body.style.backgroundColor = "#0a0a0a";
    if (root) root.style.height = "auto";
    return () => {
      html.style.height = prev.htmlHeight;
      body.style.height = prev.bodyHeight;
      body.style.backgroundColor = prev.bodyBg;
      if (root) root.style.height = prev.rootHeight;
    };
  }, []);

  return (
    <div className="bg-[#0a0a0a] text-[#f5f5f0] font-['Inter',system-ui,sans-serif] text-base leading-[1.5] antialiased overflow-x-hidden scroll-smooth">
      <Nav />
      <Hero />
      <Demo />
      <Stats />
      <Problem />
      <How />
      <Features />
      <Integrations />
      <Guardrails />
      <Feedback />
      <Footer />
    </div>
  );
};

export default HomePage;
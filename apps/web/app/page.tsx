import type { Metadata } from "next";
import Nav from "@/components/marketing/Nav";
import Hero from "@/components/marketing/Hero";
import LiveMarquee from "@/components/marketing/LiveMarquee";
import LiveSignal from "@/components/marketing/LiveSignal";
import HowItWorks from "@/components/marketing/HowItWorks";
import FreeStrip from "@/components/marketing/FreeStrip";
import Marginalia from "@/components/marketing/Marginalia";

export const metadata: Metadata = {
  title: "Telex — Autonomous Dependency Healing",
  description:
    "Autonomous dependency healing. When an npm package releases breaking changes, Telex finds every call site and opens a PR with the verified fix.",
};

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-black text-[#ECE7DA] selection:bg-white selection:text-black relative">
      {/* Illoca-Style Marginalia Coordinates & Cursor Spotlight */}
      <Marginalia />

      <Nav />
      <Hero />
      <LiveMarquee />
      <LiveSignal />
      <HowItWorks />
      <FreeStrip />

      {/* Architectural Grid Footer */}
      <footer className="py-12 px-6 sm:px-10 border-t border-white/[0.08] bg-black">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6 font-mono text-[10px] uppercase tracking-[0.2em] text-[#888888]">
          <div className="flex items-center gap-2 text-white">
            <span className="w-1.5 h-1.5 bg-white inline-block animate-pulse" />
            <span className="font-display font-bold text-xs tracking-[0.25em]">
              TELEX
            </span>
            <span className="text-[#666666]">©2026 // OPEN SOURCE</span>
          </div>

          <p className="text-center">
            AUTONOMOUS SDK & API MIGRATION DAEMON
          </p>

          <div className="flex gap-6">
            {["GITHUB", "DOCS", "ARCHITECTURE", "STATUS"].map((link) => (
              <a
                key={link}
                href="#"
                className="hover:text-white transition-colors"
              >
                {link}
              </a>
            ))}
          </div>
        </div>
      </footer>
    </main>
  );
}

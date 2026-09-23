import type { Metadata } from "next";
import Link from "next/link";
import Nav from "@/components/marketing/Nav";
import Hero from "@/components/marketing/Hero";
import LiveMarquee from "@/components/marketing/LiveMarquee";
import HowItWorks from "@/components/marketing/HowItWorks";
import FreeStrip from "@/components/marketing/FreeStrip";
import Marginalia from "@/components/marketing/Marginalia";
import { API_BASE } from "@/lib/api";

export const metadata: Metadata = {
  title: "Telex — Autonomous Self-Healing for Your Codebase",
  description:
    "Telex autonomously detects breaking changes in your dependencies and opens pull requests to fix them — before your users notice.",
};

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-black text-[#F4F4F5] selection:bg-white selection:text-black relative">
      {/* Illoca-Style Marginalia Coordinates & Cursor Spotlight */}
      <Marginalia />

      <Nav />
      <Hero />
      <LiveMarquee />
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
            <span className="text-[#7E7E8A]">©2026 // AUTONOMOUS SELF-HEALING</span>
          </div>

          <p className="text-center">
            AUTONOMOUS DEPENDENCY HEALING DAEMON // DETECTS BREAKS, OPENS PRs, SHIPS FIXES
          </p>

          <div className="flex gap-6">
            {[
              { label: "GITHUB", href: "https://github.com/Kesavaraja67/telex" },
              { label: "DASHBOARD", href: "/dashboard" },
              { label: "STATUS", href: `${API_BASE}/health` },
            ].map((link) =>
              link.href.startsWith("/") ? (
                <Link
                  key={link.label}
                  href={link.href}
                  className="hover:text-white transition-colors"
                >
                  {link.label}
                </Link>
              ) : (
                <a
                  key={link.label}
                  href={link.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-white transition-colors"
                >
                  {link.label}
                </a>
              )
            )}
          </div>
        </div>
      </footer>
    </main>
  );
}

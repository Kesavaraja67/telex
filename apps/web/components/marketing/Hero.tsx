"use client";

import dynamic from "next/dynamic";
import { motion } from "motion/react";
import { Plus_Jakarta_Sans } from "next/font/google";
import PackageMarkers from "./PackageMarkers";
import IllocaButton from "@/components/ui/IllocaButton";

const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["500", "600", "700", "800"],
});

const TelexBot3D = dynamic(() => import("./TelexBot3D"), { ssr: false });

export default function Hero() {
  const handleInstall = () => {
    const hasUser = typeof document !== "undefined" && document.cookie.includes("telex_user=");
    const appName = process.env.NEXT_PUBLIC_GITHUB_APP_NAME || "telex-agent-dev";
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    if (hasUser) {
      window.location.href = `https://github.com/apps/${appName}/installations/new`;
    } else {
      // Not signed in: redirect to login first, then automatically forward to installation
      window.location.href = `${apiUrl}/api/auth/github?next=install`;
    }
  };

  return (
    <section
      id="hero"
      className="relative flex flex-col items-center justify-center px-6 sm:px-12 pt-28 sm:pt-36 pb-16 overflow-hidden bg-black min-h-[90vh] border-b border-white/[0.08]"
    >
      {/* Background Studio Lighting Atmosphere */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 70% 50% at 65% 40%, rgba(255, 255, 255, 0.05) 0%, rgba(0, 0, 0, 0) 70%)",
        }}
      />

      <div className="relative z-10 max-w-7xl mx-auto w-full grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
        {/* Left Side: Modern Dev-Tool Startup Typography with 70-20-10 Contrast */}
        <div className="lg:col-span-6 flex flex-col items-start text-left gap-6">
          {/* Eyebrow Pill */}
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="inline-flex items-center gap-2.5 px-4 py-1.5 rounded-full border border-white/10 bg-white/[0.03] backdrop-blur-md text-[10px] font-mono text-[#8E8E93] tracking-[0.2em] uppercase"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse shadow-[0_0_6px_#ffffff]" />
            <span className="text-white font-medium">AUTONOMOUS DEPENDENCY HEALING</span>
            <span className="text-white/20">•</span>
            <span className="text-[#8E8E93]">100% FREE</span>
          </motion.div>

          {/* High-Impact Startup Headline (Plus Jakarta Sans ExtraBold) */}
          <motion.h1
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.1 }}
            className={`${jakarta.className} font-extrabold text-4xl sm:text-5xl md:text-6xl tracking-[-0.04em] leading-[1.08] text-white`}
          >
            Autonomous dependency healing{" "}
            <span className="text-silver-gradient block pt-1 drop-shadow-[0_0_30px_rgba(255,255,255,0.2)]">
              for modern codebases.
            </span>
          </motion.h1>

          {/* Subheadline in 20% Slate Gray */}
          <motion.p
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className={`${jakarta.className} text-sm sm:text-base text-[#9E9E9E] leading-relaxed max-w-lg font-normal`}
          >
            Telex proactively intercepts breaking API signature changes the moment npm releases. It parses your codebase AST and opens verified pull requests before CI ever turns red.
          </motion.p>

          {/* Dual Action Pill Buttons */}
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="flex flex-wrap items-center gap-4 pt-2"
          >
            <IllocaButton
              label="Install Telex — Free →"
              onClick={handleInstall}
              variant="primary"
            />

            <IllocaButton
              label="Pipeline [01-03] ↓"
              onClick={() => {
                const el = document.getElementById("how-it-works");
                el?.scrollIntoView({ behavior: "smooth" });
              }}
              variant="secondary"
            />
          </motion.div>

          {/* Micro Telemetry Meta */}
          <div className="flex items-center gap-6 font-mono text-[10px] text-[#71717A] uppercase tracking-widest pt-4 border-t border-white/[0.06] w-full">
            <span>ZERO AUTO-MERGE</span>
            <span>•</span>
            <span>TYPESCRIPT AST</span>
            <span>•</span>
            <span>DETERMINISTIC GATES</span>
          </div>
        </div>

        {/* Right Side: 3D WebGL Three.js Bot (Interactive Cursor Tracking) */}
        <div className="lg:col-span-6 relative flex flex-col items-center justify-center">
          {/* Ambient Glow Pod */}
          <div className="absolute w-80 h-80 rounded-full bg-white/[0.04] blur-3xl pointer-events-none" />

          {/* 3D Bot Glass Frame Container */}
          <div className="relative w-full max-w-lg aspect-[4/5] flex items-center justify-center rounded-3xl border border-white/10 bg-white/[0.015] backdrop-blur-2xl p-2 shadow-[0_25px_70px_rgba(0,0,0,0.85)] overflow-hidden group">
            {/* Subtle Kinetic Scan Line */}
            <div className="animate-scan pointer-events-none" />

            <TelexBot3D className="w-full h-full" />

            {/* Bottom Real-Time Telemetry Bar */}
            <div className="absolute bottom-3 left-4 right-4 flex items-center justify-between font-mono text-[9px] text-[#8E8E93] tracking-widest uppercase bg-black/70 backdrop-blur-md px-3.5 py-1.5 rounded-full border border-white/10 select-none pointer-events-none">
              <span className="flex items-center gap-1.5 text-white">
                <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse shadow-[0_0_6px_#ffffff]" />
                TELEX BOT // 3D WEBGL
              </span>
              <span>TRACKING: CURSOR</span>
              <span className="text-white font-medium">60 FPS</span>
            </div>
          </div>
        </div>
      </div>

      {/* Watched Packages Telemetry Grid */}
      <div className="w-full max-w-6xl mx-auto mt-16">
        <PackageMarkers />
      </div>
    </section>
  );
}

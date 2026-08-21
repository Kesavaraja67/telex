"use client";

import dynamic from "next/dynamic";
import TicketFeed from "./TicketFeed";

const StarField = dynamic(() => import("./StarField"), { ssr: false });

export default function LiveSignal() {
  return (
    <section
      id="live-signal"
      className="relative py-28 px-6 sm:px-10 overflow-hidden bg-black border-t border-white/[0.08]"
    >
      <StarField
        color1="#ffffff"
        color2="#8E8E93"
        color3="#444444"
        particleCount={45}
        speed={0.8}
        glitterIntensity={1.0}
        brightness={30}
        className="opacity-20"
      />

      <div className="relative z-10 max-w-5xl mx-auto">
        {/* Section header */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-14 pb-6 border-b border-white/[0.08]">
          <div>
            <span className="font-mono text-[10px] tracking-[0.25em] text-[#8E8E93] uppercase block mb-2 font-medium">
              [ REAL-TIME MIGRATION FEED // 02 ]
            </span>
            <h2
              className="font-header font-bold text-3xl md:text-5xl text-white tracking-[-0.035em]"
            >
              Patches landing{" "}
              <span className="text-silver-gradient">
                live.
              </span>
            </h2>
          </div>
          <div className="flex items-center gap-2 font-mono text-[11px] text-[#8E8E93]">
            <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse shadow-[0_0_6px_#ffffff]" />
            <span>LISTENING TO GLOBAL NPM REGISTRY</span>
          </div>
        </div>

        {/* Patch tickets stream */}
        <div className="flex flex-col gap-3">
          <TicketFeed />
        </div>
      </div>
    </section>
  );
}

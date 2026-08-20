"use client";

const TICKER_ITEMS = [
  { pkg: "OPENAI@4.0.0", change: "createCompletion → completions.create", status: "AUTO-PATCHED" },
  { pkg: "STRIPE@18.1.0", change: "charges.create → paymentIntents", status: "AST VALIDATED" },
  { pkg: "NEXT@15.0.0", change: "params Promise async unwrapped", status: "PR GENERATED" },
  { pkg: "DRIZZLE-ORM@0.36.0", change: "relations → foreignKey definition", status: "AUTO-PATCHED" },
  { pkg: "PRISMA@6.0.0", change: "driverAdapters explicit init", status: "AST VALIDATED" },
  { pkg: "SUPABASE@2.45.0", change: "auth.getUser session migration", status: "AUTO-PATCHED" },
  { pkg: "LANGCHAIN@0.3.0", change: "core module import splitting", status: "PR GENERATED" },
  { pkg: "AXIOS@1.7.0", change: "AbortSignal timeout unified", status: "AST VALIDATED" },
];

export default function LiveMarquee() {
  return (
    <div className="w-full overflow-hidden border-y border-white/[0.08] bg-black/60 backdrop-blur-md py-3.5 relative select-none">
      {/* Edge gradient masks */}
      <div className="absolute top-0 bottom-0 left-0 w-28 bg-gradient-to-r from-black to-transparent z-10 pointer-events-none" />
      <div className="absolute top-0 bottom-0 right-0 w-28 bg-gradient-to-l from-black to-transparent z-10 pointer-events-none" />

      {/* Infinite scrolling row */}
      <div className="flex w-max animate-marquee hover:[animation-play-state:paused] gap-4">
        {[...TICKER_ITEMS, ...TICKER_ITEMS].map((item, idx) => (
          <div
            key={idx}
            className="flex items-center gap-3 font-mono text-[11px] uppercase tracking-widest text-[#888888] px-4 py-1.5 rounded-full border border-white/10 bg-white/[0.02] backdrop-blur-md hover:border-white/30 hover:bg-white/[0.05] transition-all cursor-default"
          >
            <span className="text-white font-bold">{item.pkg}</span>
            <span className="text-white/30">•</span>
            <span className="text-[#ECE7DA] text-[10px]">{item.change}</span>
            <span className="px-2 py-0.5 text-[9px] font-bold rounded-full border border-white/20 text-white bg-white/[0.06]">
              {item.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

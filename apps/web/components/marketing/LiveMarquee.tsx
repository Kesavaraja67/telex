"use client";

const TICKER_ITEMS = [
  { label: "ENGINE B", detail: "AUTONOMOUS REVENUE RECOVERY" },
  { label: "TWO-TIER CLASSIFIER", detail: "<1MS ZERO-TOKEN FAST-PATH" },
  { label: "VERIFICATION GATE", detail: "EPHEMERAL GITHUB ACTIONS CI" },
  { label: "RAZORPAY TEST MODE", detail: "WEBHOOK & CHECKOUT VERIFIED" },
  { label: "ENGINE A", detail: "TREE-SITTER AST CODE REPAIR" },
  { label: "SAFETY POLICY", detail: "DELIBERATE STOP RETRY GUARDS" },
  { label: "HMAC VALIDATION", detail: "CRYPTOGRAPHIC SHA-256 SECRETS" },
  { label: "PR SUBSTRATE", detail: "ZERO AUTO-MERGE // HUMAN REVIEWED" },
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
            <span className="text-white font-bold">{item.label}</span>
            <span className="text-white/30">•</span>
            <span className="text-[#ECE7DA] text-[10px]">{item.detail}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

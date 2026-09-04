"use client";

const TICKER_ITEMS = [
  { pkg: "RAZORPAY CHECKOUT", change: "order_total_mismatch auto-repaired", status: "PR GENERATED" },
  { pkg: "RAZORPAY WEBHOOK", change: "X-Razorpay-Signature HMAC fix", status: "CI VERIFIED" },
  { pkg: "RAZORPAY TIMEOUT", change: "transient retry → ₹500 recovered", status: "REVENUE RECOVERED" },
  { pkg: "RAZORPAY ORDERS", change: "currency unit paise conversion patched", status: "CI VERIFIED" },
  { pkg: "RAZORPAY NODE SDK", change: "v2.9.2 orders.create signature migration", status: "AUTO-PATCHED" },
  { pkg: "RATE LIMIT GUARD", change: "bounded backoff retry (0 tokens)", status: "TIER-1 RECOVERED" },
  { pkg: "AURA DROPS DEMO", change: "checkout payment idempotency repair", status: "CI VERIFIED" },
  { pkg: "OPENAI@4.0.0", change: "createCompletion → completions.create", status: "AUTO-PATCHED" },
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

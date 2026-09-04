"use client";

import IllocaButton from "@/components/ui/IllocaButton";

export default function FreeStrip() {
  const handleInstall = () => {
    const apiUrl =
      process.env.NEXT_PUBLIC_API_URL ||
      (typeof window !== "undefined" && window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1"
        ? "https://telex-api.onrender.com"
        : "http://localhost:8000");
    window.location.href = `${apiUrl}/api/auth/github`;
  };

  return (
    <section className="relative py-28 px-6 sm:px-10 text-center overflow-hidden border-t border-white/[0.08] bg-black">
      <div className="relative z-10 max-w-4xl mx-auto flex flex-col items-center">
        <span className="font-mono text-[10px] text-[#8E8E93] tracking-[0.25em] uppercase mb-4 px-4 py-1.5 rounded-full border border-white/10 bg-white/[0.02] inline-block font-medium">
          [ 03 // RAZORPAY PAY 2026 BUILDATHON ]
        </span>

        <h2
          className="font-header font-bold text-4xl sm:text-6xl md:text-7xl text-white tracking-[-0.035em]"
        >
          Zero lost revenue.{" "}
          <span className="text-silver-gradient">
            Zero broken builds.
          </span>
        </h2>

        <p className="font-sans text-[#9E9E9E] mt-4 text-xs sm:text-sm md:text-base max-w-lg leading-relaxed">
          Built for the Razorpay Pay 2026 Buildathon. Deploy autonomous revenue recovery and self-healing patch agents to protect every transaction and keep your checkout pipeline indestructible.
        </p>

        <div className="mt-8 flex items-center justify-center">
          <IllocaButton
            label="Install Telex — Free →"
            onClick={handleInstall}
            variant="primary"
          />
        </div>

        <div className="mt-12 flex flex-wrap items-center justify-center gap-3 text-[#71717A] font-mono text-[10px] uppercase tracking-widest border-t border-white/[0.08] pt-8 w-full max-w-2xl">
          {["RAZORPAY 2026 BUILDATHON", "TWO-TIER CLASSIFIER", "AUTONOMOUS REVENUE RECOVERY", "NATIVE CI GATES"].map((tag) => (
            <span
              key={tag}
              className="px-3.5 py-1 rounded-full border border-white/10 bg-white/[0.02] backdrop-blur-md"
            >
              {tag}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

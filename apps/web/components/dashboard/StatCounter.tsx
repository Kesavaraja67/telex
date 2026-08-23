"use client";

import { useEffect, useRef } from "react";
import { animateCountUp } from "@/lib/animations";

interface StatCounterProps {
  value: number;
  label: string;
  suffix?: string;
}

export default function StatCounter({
  value,
  label,
  suffix = "",
}: StatCounterProps) {
  const numRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (numRef.current) {
      animateCountUp(numRef.current, value, suffix);
    }
  }, [value, suffix]);

  return (
    <div className="glass-surface p-6 flex flex-col gap-2 transition-all hover:border-white/25 bg-black/70 backdrop-blur-xl">
      <span
        ref={numRef}
        className="font-mono font-bold text-3xl sm:text-4xl tracking-tight text-white drop-shadow-[0_0_16px_rgba(255,255,255,0.2)]"
      >
        0{suffix}
      </span>
      <span className="font-sans text-xs text-[#A1A1AA] font-medium tracking-wide">
        {label}
      </span>
    </div>
  );
}

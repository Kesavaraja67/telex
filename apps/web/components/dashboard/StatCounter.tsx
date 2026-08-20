"use client";

import { useEffect, useRef } from "react";
import { animateCountUp } from "@/lib/animations";

interface StatCounterProps {
  value: number;
  label: string;
  suffix?: string;
  color?: "patch" | "break" | "text";
}

export default function StatCounter({
  value,
  label,
  suffix = "",
  color = "text",
}: StatCounterProps) {
  const numRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (numRef.current) {
      animateCountUp(numRef.current, value, suffix);
    }
  }, [value, suffix]);

  const colorMap = {
    patch: "#FFFFFF",
    break: "#E8A33D",
    text: "#F2F1ED",
  };

  return (
    <div className="glass-surface p-6 flex flex-col gap-2 transition-all hover:border-white/20 bg-black/60 backdrop-blur-xl">
      <span
        ref={numRef}
        className="font-mono font-bold text-3xl sm:text-4xl tracking-tight text-white"
        style={{ color: colorMap[color] }}
      >
        0{suffix}
      </span>
      <span className="font-sans text-xs text-[#8B9099] font-medium">
        {label}
      </span>
    </div>
  );
}

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
    <div className="metal-bezel p-[2px] transition-all hover:brightness-105">
      <div className="panel-inset p-5 rounded-[6px] flex flex-col justify-between gap-3">
        <div className="flex items-center justify-between">
          <span className="label-engraved text-[10px] tracking-widest">{label}</span>
          <span className="led" data-state="ok" style={{ width: "6px", height: "6px" }} />
        </div>
        <div className="bg-[#080a0c] border border-black/90 rounded px-3 py-2 shadow-[inset_0_2px_8px_rgba(0,0,0,0.95),0_1px_0_rgba(255,255,255,0.05)]">
          <span
            ref={numRef}
            className="font-mono font-bold text-3xl sm:text-4xl tracking-tight text-white drop-shadow-[0_0_14px_rgba(255,255,255,0.25)]"
          >
            0{suffix}
          </span>
        </div>
      </div>
    </div>
  );
}


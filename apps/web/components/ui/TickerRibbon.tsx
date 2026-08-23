"use client";

import React from "react";
import { motion } from "motion/react";

interface TickerRibbonProps {
  items?: string[];
  speed?: number;
  className?: string;
}

const DEFAULT_ITEMS = [
  "ENGINE B ACTIVE",
  "VERIFICATION GATE: FULL CLONE + TYPECHECK + TESTS",
  "TWO-TIER CLASSIFIER (<1MS DETERMINISTIC)",
  "REVENUE RECOVERY ACTIVE",
  "AST SYMBOL SCANNER (TREE-SITTER)",
  "DELIBERATE STOP RETRY GUARD",
  "RAZORPAY TEST MODE VERIFIED",
];

export default function TickerRibbon({
  items = DEFAULT_ITEMS,
  speed = 35,
  className = "",
}: TickerRibbonProps) {
  const repeated = [...items, ...items];

  return (
    <div className={`w-full overflow-hidden border-y border-white/[0.08] bg-black/50 backdrop-blur-md py-2.5 relative select-none ${className}`}>
      {/* Edge gradient masks */}
      <div className="absolute left-0 top-0 bottom-0 w-20 bg-gradient-to-r from-black to-transparent z-10 pointer-events-none" />
      <div className="absolute right-0 top-0 bottom-0 w-20 bg-gradient-to-l from-black to-transparent z-10 pointer-events-none" />

      <motion.div
        animate={{ x: ["0%", "-50%"] }}
        transition={{
          duration: speed,
          repeat: Infinity,
          ease: "linear",
        }}
        className="flex whitespace-nowrap gap-8 items-center"
      >
        {repeated.map((text, i) => (
          <div key={i} className="flex items-center gap-8 flex-shrink-0">
            <span className="font-mono text-[11px] tracking-widest uppercase text-[#A1A1AA] hover:text-white transition-colors">
              {text}
            </span>
            <span className="h-1 w-1 rounded-full bg-white/40" />
          </div>
        ))}
      </motion.div>
    </div>
  );
}

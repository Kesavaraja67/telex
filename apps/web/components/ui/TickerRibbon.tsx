"use client";

import React from "react";
import { motion } from "motion/react";

interface TickerRibbonProps {
  items?: string[];
  speed?: number;
  className?: string;
}

const DEFAULT_ITEMS = [
  "AUTONOMOUS SELF-HEALING ACTIVE",
  "VERIFICATION GATE: FULL CLONE + TYPECHECK + TESTS",
  "TWO-TIER CLASSIFIER (<1MS DETERMINISTIC)",
  "AUTOMATED PULL REQUEST DELIVERY",
  "AST SYMBOL SCANNER (TREE-SITTER)",
  "DELIBERATE STOP RETRY GUARD",
  "NPM & PYPI REGISTRY MONITORING",
];

export default function TickerRibbon({
  items = DEFAULT_ITEMS,
  speed = 35,
  className = "",
}: TickerRibbonProps) {
  const repeated = [...items, ...items];

  return (
    <div className={`w-full overflow-hidden panel-inset border-y border-black/80 py-2.5 relative select-none shadow-[inset_0_2px_5px_rgba(0,0,0,0.8),0_1px_0_rgba(255,255,255,0.05)] ${className}`}>
      {/* Edge gradient masks */}
      <div className="absolute left-0 top-0 bottom-0 w-20 bg-gradient-to-r from-[#0e1012] to-transparent z-10 pointer-events-none" />
      <div className="absolute right-0 top-0 bottom-0 w-20 bg-gradient-to-l from-[#0e1012] to-transparent z-10 pointer-events-none" />

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
            <span className="label-engraved text-[11px] tracking-widest uppercase hover:text-white transition-colors">
              {text}
            </span>
            <span className="led" data-state="ok" style={{ width: "5px", height: "5px" }} />
          </div>
        ))}
      </motion.div>
    </div>
  );
}


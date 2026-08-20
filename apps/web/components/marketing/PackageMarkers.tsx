"use client";

import { useState } from "react";

interface TelemetryNode {
  index: string;
  name: string;
  version: string;
  change: string;
  status: string;
}

const NODES: TelemetryNode[] = [
  {
    index: "01",
    name: "openai",
    version: "v4.0.0",
    change: "createCompletion → completions.create",
    status: "AUTO-PATCHED",
  },
  {
    index: "02",
    name: "stripe",
    version: "v18.1.0",
    change: "charges.create → paymentIntents",
    status: "AUTO-PATCHED",
  },
  {
    index: "03",
    name: "next",
    version: "v15.0.0",
    change: "params Promise async unwrapping",
    status: "AUTO-PATCHED",
  },
  {
    index: "04",
    name: "drizzle-orm",
    version: "v0.36.0",
    change: "relations → foreignKey definition",
    status: "ACTIVE SCAN",
  },
];

export default function PackageMarkers() {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  return (
    <div className="w-full max-w-4xl mx-auto grid grid-cols-1 sm:grid-cols-2 gap-3 my-2 text-left">
      {NODES.map((node, idx) => (
        <div
          key={node.name}
          onMouseEnter={() => setHoveredIdx(idx)}
          onMouseLeave={() => setHoveredIdx(null)}
          className={`p-3.5 px-4 rounded-2xl flex items-center justify-between gap-3 border transition-all duration-300 relative overflow-hidden select-none cursor-default backdrop-blur-xl ${
            hoveredIdx === idx
              ? "bg-white/[0.06] border-white/35 shadow-[0_8px_24px_rgba(255,255,255,0.08)] -translate-y-0.5"
              : "bg-white/[0.02] border-white/10"
          }`}
        >
          <div className="flex items-center gap-2.5 min-w-0">
            <span className="font-mono text-[10px] text-[#71717A]">
              [{node.index}]
            </span>
            <div className="flex items-baseline gap-2 min-w-0 truncate">
              <span className="font-mono text-xs font-bold text-white tracking-tight uppercase">
                {node.name}
              </span>
              <span className="font-mono text-[10px] text-[#8E8E93]">
                {node.version}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            <span className="font-mono text-[9px] text-[#9E9E9E] transition-colors hidden md:inline truncate max-w-[140px]">
              {node.change}
            </span>
            <span
              className={`font-mono text-[9px] font-bold px-2.5 py-0.5 rounded-full border uppercase tracking-wider transition-all duration-300 ${
                hoveredIdx === idx
                  ? "border-white text-black bg-white shadow-sm"
                  : "border-white/20 text-[#E4E4E7] bg-white/[0.04]"
              }`}
            >
              {node.status}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

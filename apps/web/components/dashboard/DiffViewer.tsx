"use client";

import { useEffect, useRef } from "react";
import { animateDiffReveal } from "@/lib/animations";

interface DiffViewerProps {
  diff: string;
  filename?: string;
  animated?: boolean;
}

export default function DiffViewer({ diff, filename, animated = true }: DiffViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!animated || !containerRef.current) return;
    const chars = containerRef.current.querySelectorAll(".char");
    animateDiffReveal(chars as NodeListOf<Element>);
  }, [diff, animated]);

  const lines = diff.split("\n");

  function renderLine(line: string, idx: number) {
    const chars = line.split("").map((ch, i) => (
      <span key={i} className="char" style={{ opacity: animated ? 0 : 1 }}>
        {ch}
      </span>
    ));

    let className = "text-[#8B9099]";
    let bg = "transparent";
    if (line.startsWith("+")) {
      className = "text-[#4FD1C5]";
      bg = "rgba(79, 209, 197, 0.08)";
    } else if (line.startsWith("-")) {
      className = "text-[#E8A33D]";
      bg = "rgba(232, 163, 61, 0.08)";
    }

    return (
      <div
        key={idx}
        className={`${className} px-4 py-0.5 text-xs font-mono leading-5`}
        style={{ background: bg }}
      >
        {chars}
      </div>
    );
  }

  return (
    <div className="glass-surface overflow-hidden bg-black/80 border border-white/[0.08]">
      {filename && (
        <div className="px-4 py-2.5 font-mono text-xs text-[#8B9099] flex items-center gap-2 border-b border-white/[0.08] bg-white/[0.02]">
          <span className="text-white font-medium">DIFF</span>
          <span className="text-[#F2F1ED]">{filename}</span>
        </div>
      )}
      <div ref={containerRef} className="py-2.5">
        {lines.map((line, i) => renderLine(line, i))}
      </div>
    </div>
  );
}

"use client";

import { useEffect, useRef } from "react";
import { animateDiffReveal } from "@/lib/animations";

interface DiffViewerProps {
  diff: string;
  filename?: string;
  animated?: boolean;
}

const CHAR_ANIMATION_SIZE_LIMIT = 300;

export default function DiffViewer({ diff, filename, animated = true }: DiffViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const shouldAnimate = animated && diff.length <= CHAR_ANIMATION_SIZE_LIMIT;

  useEffect(() => {
    if (!shouldAnimate || !containerRef.current) return;
    const chars = containerRef.current.querySelectorAll(".char");
    animateDiffReveal(chars as NodeListOf<Element>).catch(() => {
      chars.forEach((c) => {
        (c as HTMLElement).style.opacity = "1";
      });
    });
  }, [diff, shouldAnimate]);

  const lines = diff.split("\n");

  function renderLine(line: string, idx: number) {
    let className = "text-[#A1A1AA]";
    let bg = "transparent";
    if (line.startsWith("+")) {
      className = "text-white font-medium";
      bg = "rgba(255, 255, 255, 0.1)";
    } else if (line.startsWith("-")) {
      className = "text-[#71717A] line-through";
      bg = "rgba(255, 255, 255, 0.02)";
    }

    const content = shouldAnimate
      ? line.split("").map((ch, i) => (
          <span key={i} className="char" style={{ opacity: 0 }}>
            {ch}
          </span>
        ))
      : line;

    return (
      <div
        key={idx}
        className={`${className} px-4 py-0.5 text-xs font-mono leading-5 whitespace-pre overflow-x-visible`}
        style={{ background: bg }}
      >
        {content}
      </div>
    );
  }

  return (
    <div className="rounded-lg overflow-hidden border border-white/10 bg-black">
      {filename && (
        <div className="px-4 py-2 bg-white/[0.04] border-b border-white/[0.08] flex items-center justify-between">
          <span className="font-mono text-xs text-white">{filename}</span>
          <span className="font-mono text-[10px] text-[#71717A]">UNIFIED DIFF</span>
        </div>
      )}
      <div ref={containerRef} className="py-2 overflow-x-auto">
        {lines.map((l, i) => renderLine(l, i))}
      </div>
    </div>
  );
}

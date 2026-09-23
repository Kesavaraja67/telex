"use client";

import React from "react";
import type { PatchSummary } from "@/lib/api";

export type SortMode =
  | "all"
  | "semantic-risk-first"
  | "high-confidence"
  | "needs-review";

export const SORT_MODES: { value: SortMode; label: string }[] = [
  { value: "all", label: "All Patches" },
  { value: "semantic-risk-first", label: "Semantic Risk First" },
  { value: "high-confidence", label: "High Confidence" },
  { value: "needs-review", label: "Needs Review" },
];

/**
 * Sort and filter a patch list according to the active triage mode.
 *
 * Modes:
 * - `"all"`: preserve the original DB order (no-op).
 * - `"semantic-risk-first"`: semantic-risk patches first, then by confidence desc.
 * - `"high-confidence"`: confidence descending, opened_at as tie-break.
 * - `"needs-review"`: hide merged/verified/closed; surface semantic-risk or
 *   patches where tests_passed or typecheck_passed is not true.
 */
function sortedAndFiltered(
  patches: PatchSummary[],
  mode: SortMode,
): PatchSummary[] {
  let result = patches;

  // Filter
  if (mode === "needs-review") {
    result = patches.filter(
      (p) =>
        p.status !== "merged" &&
        p.status !== "verified" &&
        p.status !== "closed" &&
        (p.is_semantic_risk === true || p.tests_passed !== true || p.typecheck_passed !== true),
    );
  }

  // Sort
  if (mode === "semantic-risk-first") {
    result = [...result].sort((a, b) => {
      const aRisk = a.is_semantic_risk === true ? 1 : 0;
      const bRisk = b.is_semantic_risk === true ? 1 : 0;
      if (aRisk !== bRisk) return bRisk - aRisk;
      // Within same risk tier: higher confidence first
      const aConf = a.confidence ?? 0;
      const bConf = b.confidence ?? 0;
      return bConf - aConf;
    });
  } else if (mode === "high-confidence") {
    result = [...result].sort((a, b) => {
      const aConf = a.confidence ?? 0;
      const bConf = b.confidence ?? 0;
      if (aConf !== bConf) return bConf - aConf;
      // Tie-break: newer first
      return new Date(b.opened_at).getTime() - new Date(a.opened_at).getTime();
    });
  } else {
    // "all": keep original DB order (created_at desc) — untouched
  }

  return result;
}

interface PatchSortControlsProps {
  activeMode: SortMode;
  onModeChange: (mode: SortMode) => void;
  patchCount: number;
}

export default function PatchSortControls({
  activeMode,
  onModeChange,
  patchCount,
}: PatchSortControlsProps) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className="font-mono text-[10px] text-[#8B9099] uppercase tracking-wider">
        Sort:
      </span>
      {SORT_MODES.map(({ value, label }) => (
        <button
          key={value}
          type="button"
          onClick={() => onModeChange(value)}
          className={`font-mono text-[11px] px-2.5 py-1 rounded-full border transition-all cursor-pointer ${
            activeMode === value
              ? "bg-white text-black border-white font-semibold shadow-sm"
              : "bg-black/50 text-[#A1A1AA] border-white/[0.10] hover:text-white hover:border-white/30"
          }`}
          aria-pressed={activeMode === value}
        >
          {label}
        </button>
      ))}
      <span className="font-mono text-[10px] text-[#71717A] ml-1">
        ({patchCount} patch{patchCount !== 1 ? "es" : ""})
      </span>
    </div>
  );
}

export { sortedAndFiltered as sortPatches };

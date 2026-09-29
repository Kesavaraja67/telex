"use client";

import React, { useState } from "react";
import Link from "next/link";
import type { RepoAnalysisHistory, RepoAnalysisRun, AnalysisFinding } from "@/lib/api";

interface RunAnalysisCardProps {
  repoId: string;
  repoName: string;
  history: RepoAnalysisHistory | null;
  isLoading: boolean;
  error?: string | null;
  onTriggerAnalysis: () => Promise<void>;
}

export function RunAnalysisCard({
  repoId,
  repoName,
  history,
  isLoading,
  error,
  onTriggerAnalysis,
}: RunAnalysisCardProps) {
  const [selectedFinding, setSelectedFinding] = useState<number | null>(null);

  const buildAtlasLink = (deepLink?: string) => {
    const params = new URLSearchParams();
    params.set("repo", repoId);
    if (deepLink) {
      const searchPart = deepLink.startsWith("?") ? deepLink.slice(1) : deepLink;
      const parsed = new URLSearchParams(searchPart);
      parsed.forEach((val, key) => {
        params.set(key, val);
      });
    }
    return `/dashboard/atlas?${params.toString()}`;
  };

  const latest: RepoAnalysisRun | null = history?.latest || null;
  const previous = history?.previous || null;
  const deltaScore = history?.delta_score ?? 0;

  const score = latest?.score ?? 0;
  // Map score [0..100] to needle angle [-130deg .. +130deg]
  const needleAngle = -130 + (Math.max(0, Math.min(100, score)) / 100) * 260;

  const getScoreVerdict = (s: number) => {
    if (s >= 88) return { label: "PRISTINE", color: "#10B981", text: "text-emerald-400" };
    if (s >= 75) return { label: "NOMINAL", color: "#14B8A6", text: "text-teal-400" };
    if (s >= 50) return { label: "ELEVATED RISK", color: "#F59E0B", text: "text-amber-400" };
    return { label: "CRITICAL ACTION", color: "#E11D48", text: "text-rose-400" };
  };

  const verdict = getScoreVerdict(score);

  return (
    <div className="p-6 bg-black/75 backdrop-blur-xl border border-white/15 relative overflow-hidden flex flex-col gap-6 rounded-2xl shadow-2xl">
      {error && (
        <div className="p-3 bg-red-950/40 border border-red-500/30 rounded-lg flex items-center gap-2 text-red-200 text-xs font-mono relative z-10">
          <span>⚠️</span>
          <span>{error}</span>
        </div>
      )}
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.08] pb-4 relative z-10">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-white/10 border border-white/20 flex items-center justify-center font-mono text-xs font-bold text-white shadow-inner">
            ⚡
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-mono font-semibold text-base text-white tracking-tight">
                Architectural Risk &amp; Resilience Radar
              </h2>
              <span className="badge-chip font-mono text-[10px] px-2 py-0.5 rounded bg-white/10 text-white/80 border border-white/15">
                Deterministic Phase 4
              </span>
            </div>
            <p className="font-mono text-xs text-[#71717A] mt-0.5">
              Strictly fact-grounded AST graph, circularity, and dependency verification.
            </p>
          </div>
        </div>

        <button
          onClick={onTriggerAnalysis}
          disabled={isLoading}
          className="font-mono text-xs font-semibold px-4 py-2 rounded-xl bg-white text-black hover:bg-white/90 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-2 self-start sm:self-auto shadow-md cursor-pointer"
        >
          {isLoading ? (
            <span className="flex items-center gap-2">
              <span className="w-3.5 h-3.5 rounded-full border-2 border-black/30 border-t-black animate-spin" />
              <span>Analyzing AST &amp; Graph…</span>
            </span>
          ) : (
            <>
              <span>Re-Analyze Architecture</span>
              <span>⚡</span>
            </>
          )}
        </button>
      </div>

      {/* Loading state skeleton overlay */}
      {isLoading && (
        <div className="p-8 rounded-xl border border-white/10 bg-black/60 relative overflow-hidden flex flex-col items-center justify-center text-center gap-3.5 my-2">
          <div className="relative w-16 h-16 flex items-center justify-center">
            <div className="absolute inset-0 rounded-full border border-white/10 animate-ping opacity-25" />
            <div className="absolute inset-2 rounded-full border border-white/20 animate-pulse" />
            <div className="absolute inset-0 rounded-full border border-dashed border-white/40 animate-spin [animation-duration:5s]" />
            <span className="w-3 h-3 rounded-full bg-cyan-400 shadow-[0_0_12px_rgba(34,211,238,0.8)]" />
          </div>
          <div className="flex flex-col items-center gap-1 font-mono text-xs">
            <span className="text-white font-bold uppercase tracking-wider flex items-center gap-2">
              Computing Tarjan SCC &amp; Graph Boundary Signals
            </span>
            <span className="text-[11px] text-[#A1A1AA]">
              Calculating deterministic sub-scores for {repoName}…
            </span>
          </div>
        </div>
      )}

      {/* Empty / First Run State */}
      {!latest && !isLoading && (
        <div className="p-8 rounded-xl border border-dashed border-white/20 bg-white/[0.02] flex flex-col items-center justify-center text-center gap-4 py-12">
          <div className="w-12 h-12 rounded-full bg-white/5 border border-white/10 flex items-center justify-center text-xl text-white/60">
            📊
          </div>
          <div className="max-w-md flex flex-col gap-1.5">
            <h3 className="font-mono text-sm font-semibold text-white">
              No Analysis Recorded Yet
            </h3>
            <p className="font-mono text-xs text-[#71717A] leading-relaxed">
              Run an evidence-based scan to analyze circular dependencies, hub file fan-in, test presence, and upstream breaking changes.
            </p>
          </div>
          <button
            onClick={onTriggerAnalysis}
            className="font-mono text-xs font-semibold px-4 py-2 rounded-lg bg-white text-black hover:bg-white/90 transition-all cursor-pointer shadow-lg"
          >
            Run First Analysis Now →
          </button>
        </div>
      )}

      {/* Main Analysis Display */}
      {latest && !isLoading && (
        <div className="flex flex-col gap-6">
          {/* Upper Deck: Physical Analog Meter & 4 Sub-Gauges */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
            {/* Left Instrument: Analog Score Meter (5 cols) */}
            <div className="lg:col-span-5 p-5 rounded-2xl bg-black/60 border border-white/10 flex flex-col items-center justify-between relative shadow-inner">
              <div className="w-full flex items-center justify-between font-mono text-[11px] text-[#71717A] pb-2 border-b border-white/5">
                <span className="uppercase tracking-wider">Health Meter</span>
                {deltaScore !== 0 && (
                  <span
                    className={`px-2 py-0.5 rounded-full font-bold text-[10px] flex items-center gap-1 ${
                      deltaScore > 0
                        ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                        : "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                    }`}
                  >
                    <span>{deltaScore > 0 ? "▲ +" : "▼ "}</span>
                    <span>{deltaScore} vs prev</span>
                  </span>
                )}
                {deltaScore === 0 && previous && (
                  <span className="px-2 py-0.5 rounded-full bg-white/5 text-[#A1A1AA] border border-white/10 text-[10px]">
                    ±0 unchanged
                  </span>
                )}
              </div>

              {/* The Dial Bezel Container */}
              <div className="relative w-56 h-48 my-3 flex items-center justify-center">
                {/* SVG Dial Arc Background */}
                <svg className="w-56 h-48 overflow-visible" viewBox="0 0 200 170">
                  <defs>
                    <linearGradient id="gaugeGradient" x1="0%" y1="100%" x2="100%" y2="100%">
                      <stop offset="0%" stopColor="#E11D48" />
                      <stop offset="45%" stopColor="#F59E0B" />
                      <stop offset="75%" stopColor="#10B981" />
                      <stop offset="100%" stopColor="#06B6D4" />
                    </linearGradient>
                  </defs>

                  {/* Outer Bezel Rim */}
                  <circle
                    cx="100"
                    cy="105"
                    r="85"
                    fill="none"
                    stroke="rgba(255,255,255,0.06)"
                    strokeWidth="12"
                  />

                  {/* Track Arc (260 degree arc) */}
                  <path
                    d="M 35 155 A 80 80 0 1 1 165 155"
                    fill="none"
                    stroke="rgba(255,255,255,0.12)"
                    strokeWidth="8"
                    strokeLinecap="round"
                  />

                  {/* Colored Value Arc */}
                  <path
                    d="M 35 155 A 80 80 0 1 1 165 155"
                    fill="none"
                    stroke="url(#gaugeGradient)"
                    strokeWidth="8"
                    strokeLinecap="round"
                    strokeDasharray="360"
                    strokeDashoffset={360 - (score / 100) * 360}
                    className="transition-all duration-700 ease-out"
                  />

                  {/* Tick Marks & Scale Numerals */}
                  <text x="25" y="165" fill="#71717A" fontSize="9" fontFamily="monospace">0</text>
                  <text x="35" y="75" fill="#71717A" fontSize="9" fontFamily="monospace">25</text>
                  <text x="95" y="45" fill="#71717A" fontSize="9" fontFamily="monospace">50</text>
                  <text x="155" y="75" fill="#71717A" fontSize="9" fontFamily="monospace">75</text>
                  <text x="165" y="165" fill="#71717A" fontSize="9" fontFamily="monospace">100</text>
                </svg>

                {/* The Physical Rotating Needle */}
                <div
                  className="absolute bottom-[25px] w-2 h-20 origin-bottom transition-transform duration-700 ease-out flex flex-col items-center pointer-events-none"
                  style={{
                    transform: `rotate(${needleAngle}deg)`,
                  }}
                >
                  {/* Needle Blade */}
                  <div
                    className="w-1 h-20 bg-gradient-to-t from-white/90 via-red-500 to-rose-400 rounded-t shadow-[0_0_8px_rgba(244,63,94,0.6)]"
                    style={{ clipPath: "polygon(50% 0%, 0% 100%, 100% 100%)" }}
                  />
                </div>

                {/* Center Pivot Cap */}
                <div className="absolute bottom-[17px] w-6 h-6 rounded-full bg-gradient-to-b from-[#2E3136] to-[#141618] border border-white/30 shadow-[0_2px_6px_rgba(0,0,0,0.8)] flex items-center justify-center">
                  <div className="w-2 h-2 rounded-full bg-white/40 shadow-inner" />
                </div>
              </div>

              {/* Digital readout below needle */}
              <div className="flex flex-col items-center gap-0.5 mt-[-10px]">
                <div className="flex items-baseline gap-1">
                  <span className="font-mono text-3xl font-extrabold text-white tracking-tight">
                    {score}
                  </span>
                  <span className="font-mono text-xs text-[#71717A]">/100</span>
                </div>
                <span className={`font-mono text-xs font-bold tracking-wider ${verdict.text}`}>
                  {verdict.label}
                </span>
              </div>
            </div>

            {/* Right Instrument: 4 Weighted Sub-Score Gauges (7 cols) */}
            <div className="lg:col-span-7 p-5 rounded-2xl bg-black/60 border border-white/10 flex flex-col justify-between gap-4">
              <div className="flex items-center justify-between pb-2 border-b border-white/5 font-mono text-[11px] text-[#71717A]">
                <span className="uppercase tracking-wider">Sub-Score Breakdown</span>
                <span className="text-[10px]">Deterministic Weights (100% Sum)</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 flex-1">
                {/* 1. Structure (30%) */}
                <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/5 flex flex-col justify-between gap-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-semibold text-white">Structure</span>
                    <span className="font-mono text-[10px] text-[#71717A]">Weight: 30%</span>
                  </div>
                  <div className="flex items-baseline justify-between">
                    <span className="font-mono text-xl font-bold text-white">
                      {latest.sub_scores.structure !== null ? `${latest.sub_scores.structure}/100` : "Not Measured"}
                    </span>
                    <span className="font-mono text-[10px] text-[#A1A1AA]">
                      {latest.signals?.structure?.cycles_count ?? 0} cycles
                    </span>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-white/10 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-blue-500 to-cyan-400 transition-all duration-500"
                      style={{ width: `${latest.sub_scores.structure ?? 0}%` }}
                    />
                  </div>
                </div>

                {/* 2. Dependency Health (30%) */}
                <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/5 flex flex-col justify-between gap-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-semibold text-white">Dependency Health</span>
                    <span className="font-mono text-[10px] text-[#71717A]">Weight: 30%</span>
                  </div>
                  <div className="flex items-baseline justify-between">
                    <span className="font-mono text-xl font-bold text-white">
                      {latest.sub_scores.dependency !== null ? `${latest.sub_scores.dependency}/100` : "Not Measured"}
                    </span>
                    <span className="font-mono text-[10px] text-[#A1A1AA]">
                      {latest.signals?.dependency?.breaking_changes_count ?? 0} breaking
                    </span>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-white/10 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-emerald-500 to-teal-400 transition-all duration-500"
                      style={{ width: `${latest.sub_scores.dependency ?? 0}%` }}
                    />
                  </div>
                </div>

                {/* 3. Change Safety (25%) */}
                <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/5 flex flex-col justify-between gap-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-semibold text-white">Change Safety</span>
                    <span className="font-mono text-[10px] text-[#71717A]">Weight: 25%</span>
                  </div>
                  <div className="flex items-baseline justify-between">
                    <span className="font-mono text-xl font-bold text-white">
                      {latest.sub_scores.change_safety !== null ? `${latest.sub_scores.change_safety}/100` : "Not Measured"}
                    </span>
                    <span className="font-mono text-[10px] text-[#A1A1AA]">
                      {latest.signals?.change_safety?.has_tests ? "Tests OK" : "No Tests"} · {latest.signals?.change_safety?.has_ci ? "CI OK" : "No CI"}
                    </span>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-white/10 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-amber-500 to-yellow-400 transition-all duration-500"
                      style={{ width: `${latest.sub_scores.change_safety ?? 0}%` }}
                    />
                  </div>
                </div>

                {/* 4. Verification (15%) */}
                <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/5 flex flex-col justify-between gap-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-semibold text-white">Verification</span>
                    <span className="font-mono text-[10px] text-[#71717A]">Weight: 15%</span>
                  </div>
                  <div className="flex items-baseline justify-between">
                    <span className="font-mono text-xl font-bold text-white">
                      {latest.sub_scores.verification !== null ? `${latest.sub_scores.verification}/100` : "Not Measured"}
                    </span>
                    <span className="font-mono text-[10px] text-[#A1A1AA]">
                      {latest.signals?.verification?.merged_prs_count ?? 0} PRs merged
                    </span>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-white/10 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-purple-500 to-pink-400 transition-all duration-500"
                      style={{ width: `${latest.sub_scores.verification ?? 0}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Executive Summary Prose (LLM synthesised strictly from facts) */}
          {latest.executive_summary && (
            <div className="p-4 rounded-xl bg-white/[0.02] border border-white/10 flex flex-col gap-1.5">
              <span className="font-mono text-[10px] text-[#71717A] uppercase tracking-wider">
                Executive Architecture Summary
              </span>
              <p className="font-sans text-xs text-white/90 leading-relaxed">
                {latest.executive_summary}
              </p>
            </div>
          )}

          {/* Do This First Action List */}
          {latest.do_this_first && latest.do_this_first.length > 0 && (
            <div className="p-4 rounded-xl bg-cyan-500/[0.03] border border-cyan-500/20 flex flex-col gap-2.5">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_8px_rgba(34,211,238,0.8)]" />
                <span className="font-mono text-xs font-bold text-cyan-300 uppercase tracking-wider">
                  Do This First (Prioritized Actions)
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pl-4">
                {latest.do_this_first.map((item, idx) => (
                  <div
                    key={idx}
                    className="flex items-start gap-2.5 p-2 rounded-lg bg-black/40 border border-white/5 font-mono text-xs text-white"
                  >
                    <span className="font-bold text-cyan-400 flex-shrink-0">
                      {idx + 1}.
                    </span>
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Findings List with Deep Links into 3D Atlas */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between pb-1 border-b border-white/5 font-mono text-xs">
              <span className="font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                <span>Verified Findings</span>
                <span className="px-2 py-0.5 rounded-full bg-white/10 text-white text-[10px]">
                  {latest.findings.length}
                </span>
              </span>
              <span className="text-[11px] text-[#71717A]">
                Click any finding to inspect in 3D Atlas
              </span>
            </div>

            {latest.findings.length === 0 ? (
              <div className="p-4 rounded-xl border border-white/10 bg-black/40 text-center font-mono text-xs text-emerald-400">
                ✓ No critical structural bottlenecks or breaking cycles detected.
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-2.5">
                {latest.findings.map((f: AnalysisFinding, idx: number) => {
                  const isExpanded = selectedFinding === idx;
                  const severityStyle =
                    f.severity === "critical"
                      ? { bg: "bg-rose-500/10", border: "border-rose-500/30", text: "text-rose-400", led: "bg-rose-500" }
                      : f.severity === "warning"
                      ? { bg: "bg-amber-500/10", border: "border-amber-500/30", text: "text-amber-400", led: "bg-amber-500" }
                      : { bg: "bg-cyan-500/10", border: "border-cyan-500/30", text: "text-cyan-400", led: "bg-cyan-500" };

                  return (
                    <div
                      key={idx}
                      className={`p-3.5 rounded-xl border transition-all flex flex-col gap-2 ${severityStyle.bg} ${severityStyle.border}`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <span
                            className={`w-2 h-2 rounded-full ${severityStyle.led} shadow-[0_0_6px_currentColor] flex-shrink-0`}
                          />
                          <span className="font-mono text-xs font-bold text-white truncate">
                            {f.title}
                          </span>
                        </div>

                        <div className="flex items-center gap-2 flex-shrink-0">
                          {f.atlas_deep_link && (
                            <Link
                              href={buildAtlasLink(f.atlas_deep_link)}
                              className="px-2.5 py-1 rounded-lg bg-white/10 hover:bg-white text-white hover:text-black font-mono text-[10px] font-semibold transition-all flex items-center gap-1 cursor-pointer shadow-sm"
                            >
                              <span>Atlas View</span>
                              <span>↗</span>
                            </Link>
                          )}
                          <button
                            type="button"
                            onClick={() => setSelectedFinding(isExpanded ? null : idx)}
                            className="font-mono text-[11px] text-[#A1A1AA] hover:text-white px-1.5 py-0.5 rounded cursor-pointer"
                          >
                            {isExpanded ? "▲ Hide" : "▼ Details"}
                          </button>
                        </div>
                      </div>

                      {/* Expanded Evidence & Remediation */}
                      {isExpanded && (
                        <div className="pt-2 border-t border-white/10 flex flex-col gap-2 font-mono text-xs">
                          <div>
                            <span className="text-[10px] text-[#71717A] uppercase">Why it matters:</span>
                            <p className="text-white/90 text-xs mt-0.5 leading-relaxed">
                              {f.why_it_matters}
                            </p>
                          </div>
                          <div>
                            <span className="text-[10px] text-[#71717A] uppercase">Recommended Action:</span>
                            <p className="text-cyan-300 text-xs mt-0.5 leading-relaxed font-semibold">
                              {f.what_to_do}
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

"use client";

import React, { useState, useEffect, use } from "react";
import Link from "next/link";
import { motion } from "motion/react";
import SpotlightCard from "@/components/ui/SpotlightCard";
import BorderBeam from "@/components/ui/BorderBeam";
import CyberGridBackground from "@/components/ui/CyberGridBackground";
import { CyberSkeletonPatch } from "@/components/ui/CyberSkeleton";
import DiffViewer from "@/components/dashboard/DiffViewer";
import type { RepoDetails, AIExplanation, PatchSummary } from "@/lib/api";

export default function RepoDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const resolvedParams = use(params);
  const repoId = resolvedParams.id;

  const [repo, setRepo] = useState<RepoDetails | null>(null);
  const [patches, setPatches] = useState<PatchSummary[]>([]);
  const [selectedPatchIndex, setSelectedPatchIndex] = useState<number>(0);
  const [aiExplanation, setAiExplanation] = useState<AIExplanation | null>(null);
  const [aiError, setAiError] = useState<string | null>(null);
  const [isLoadingAi, setIsLoadingAi] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    let timer: NodeJS.Timeout | null = null;
    let isMounted = true;

    async function loadData() {
      if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
      try {
        const { getRepoDetails, getRepoPatches } = await import("@/lib/api");
        const [repoData, patchesData] = await Promise.allSettled([
          getRepoDetails(repoId),
          getRepoPatches(repoId),
        ]);

        if (!isMounted) return;

        if (repoData.status === "fulfilled" && repoData.value) {
          setRepo(repoData.value);
          setNotFound(false);
        } else {
          setNotFound(true);
        }

        if (patchesData.status === "fulfilled" && patchesData.value?.patches) {
          setPatches(patchesData.value.patches);
        }
      } catch {
        if (isMounted) {
          setNotFound(true);
        }
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    loadData();
    timer = setInterval(loadData, 15000);

    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        loadData();
      }
    };
    if (typeof document !== "undefined") {
      document.addEventListener("visibilitychange", onVisibilityChange);
    }

    return () => {
      isMounted = false;
      if (timer) clearInterval(timer);
      if (typeof document !== "undefined") {
        document.removeEventListener("visibilitychange", onVisibilityChange);
      }
    };
  }, [repoId]);

  async function handleRunGeminiExplain() {
    setIsLoadingAi(true);
    setAiError(null);
    try {
      const { explainRepoWithGemini } = await import("@/lib/api");
      const result = await explainRepoWithGemini(repoId);
      setAiExplanation(result);
    } catch (err: any) {
      setAiExplanation(null);
      setAiError(err?.message || "Failed to generate live Gemini analysis. Please verify API configuration.");
    } finally {
      setIsLoadingAi(false);
    }
  }

  // State 1: Loading
  if (isLoading && !repo) {
    return (
      <div className="relative z-10 w-full" role="status" aria-label="Loading repository telemetry">
        <CyberGridBackground />
        <CyberSkeletonPatch />
      </div>
    );
  }

  // Not found
  if (notFound || !repo) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] p-4 text-center">
        <CyberGridBackground />
        <SpotlightCard
          spotlightColor="rgba(255, 255, 255, 0.08)"
          className="p-8 sm:p-12 bg-black/80 backdrop-blur-2xl border border-white/15 rounded-2xl flex flex-col items-center text-center gap-5 max-w-md w-full shadow-2xl"
          enableTilt={false}
        >
          <div className="w-14 h-14 rounded-2xl bg-white/5 border border-white/15 flex items-center justify-center text-white">
            <svg
              className="w-7 h-7 stroke-current"
              viewBox="0 0 24 24"
              fill="none"
              strokeWidth="1.5"
              aria-hidden="true"
            >
              <rect width="18" height="18" x="3" y="3" rx="2" />
              <line x1="9" y1="9" x2="15" y2="15" />
              <line x1="15" y1="9" x2="9" y2="15" />
            </svg>
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA]">
              Target Not Found // 404
            </span>
            <h2 className="font-mono text-lg font-bold text-white">
              Repository Not Registered
            </h2>
            <p className="font-sans text-xs text-[#A1A1AA] leading-relaxed">
              This repository is either not authorized via the Telex GitHub App or has been removed from monitored targets.
            </p>
          </div>
          <Link
            href="/dashboard/repos"
            className="px-4 py-2 rounded-lg bg-white text-black font-mono font-bold text-xs hover:bg-white/90 transition-all shadow-md active:scale-[0.98]"
          >
            ← Back to Repositories
          </Link>
        </SpotlightCard>
      </div>
    );
  }

  const activePatch = patches[selectedPatchIndex] || null;

  return (
    <div className="flex flex-col gap-6 relative z-10 max-w-7xl mx-auto w-full">
      <CyberGridBackground />

      {/* Header & Navigation */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 font-mono text-xs text-[#71717A]">
            <Link href="/dashboard" className="hover:text-white transition-colors">
              Fleet Overview
            </Link>
            <span className="text-[#3F3F46]">/</span>
            <Link href="/dashboard/repos" className="hover:text-white transition-colors">
              Repositories
            </Link>
            <span className="text-[#3F3F46]">/</span>
            <span className="text-white font-medium">{repo.name || repo.full_name}</span>
          </div>

          <div className="flex items-center gap-3">
            <h1 className="font-mono font-bold text-xl sm:text-2xl text-white tracking-tight">
              {repo.full_name}
            </h1>
            <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-white/10 text-[#A1A1AA] border border-white/15">
              {repo.default_branch}
            </span>
          </div>

          {repo.description && (
            <p className="font-sans text-xs text-[#71717A] max-w-2xl">
              {repo.description}
            </p>
          )}
        </div>

        {/* GitHub Link & Policy Badge */}
        <div className="flex items-center gap-2.5 self-start sm:self-center">
          <Link
            href="/dashboard/repos"
            className="font-mono text-xs px-3 py-1.5 rounded-lg border border-white/15 bg-white/[0.04] text-[#A1A1AA] hover:text-white hover:border-white/30 transition-all"
          >
            Policy Settings
          </Link>

          {repo.github_url && (
            <Link
              href={repo.github_url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-xs px-3.5 py-1.5 rounded-lg bg-white text-black hover:bg-white/90 transition-all flex items-center gap-1.5 shadow-sm font-semibold"
            >
              <span>GitHub</span>
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </Link>
          )}
        </div>
      </div>

      {/* Section: Autonomous Breaking Changes & Patch Verification */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="font-mono font-semibold text-sm text-white tracking-tight">
              Detected Breaking Changes & Patches
            </h2>
            <span className="font-mono text-[10px] px-2 py-0.5 rounded-full bg-white/10 text-[#A1A1AA] border border-white/15">
              {patches.length} detected
            </span>
          </div>
        </div>

        {/* State 2: Empty State for Patches */}
        {patches.length === 0 ? (
          <SpotlightCard
            spotlightColor="rgba(255, 255, 255, 0.05)"
            className="p-8 sm:p-10 bg-black/60 backdrop-blur-xl border border-white/10 rounded-xl flex flex-col items-center text-center gap-3"
            enableTilt={false}
          >
            <div className="w-12 h-12 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-white">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div className="flex flex-col gap-1 max-w-md">
              <h3 className="font-mono font-bold text-sm text-white">
                No issues detected yet
              </h3>
              <p className="font-sans text-xs text-[#A1A1AA] leading-relaxed">
                Telex checks this repo whenever a dependency you use ships a breaking change.
              </p>
            </div>
          </SpotlightCard>
        ) : (
          /* State 3: Populated Patches + Live Validation Disclosure */
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            {/* Left list: Patches */}
            <div className="lg:col-span-4 flex flex-col gap-2">
              {patches.map((patch, idx) => (
                <button
                  key={patch.id}
                  onClick={() => setSelectedPatchIndex(idx)}
                  className={`p-3 rounded-xl border text-left transition-all flex flex-col gap-1.5 cursor-pointer ${
                    selectedPatchIndex === idx
                      ? "bg-white/[0.08] border-white/30 shadow-md"
                      : "bg-black/50 border-white/[0.08] hover:border-white/20"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs font-bold text-white truncate">
                      {patch.package}
                    </span>
                    <span className="font-mono text-[9px] px-1.5 py-0.5 rounded bg-white/10 text-white border border-white/15 flex-shrink-0">
                      {patch.status}
                    </span>
                  </div>

                  {patch.change_description && (
                    <p className="font-sans text-[11px] text-[#A1A1AA] line-clamp-2">
                      {patch.change_description}
                    </p>
                  )}

                  <div className="flex items-center justify-between pt-1 border-t border-white/[0.04] font-mono text-[10px] text-[#71717A]">
                    <span>
                      Mode:{" "}
                      <span className="text-white/80">
                        {patch.verification_mode === "full" ? "Full Sandbox" : "AST Structural"}
                      </span>
                    </span>
                    <span>{new Date(patch.opened_at).toLocaleDateString()}</span>
                  </div>
                </button>
              ))}
            </div>

            {/* Right details: Selected Patch Detail & Diff Viewer */}
            <div className="lg:col-span-8 flex flex-col gap-3">
              {activePatch && (
                <SpotlightCard
                  spotlightColor="rgba(255, 255, 255, 0.05)"
                  className="p-4 sm:p-5 bg-black/70 backdrop-blur-xl border border-white/15 rounded-xl flex flex-col gap-4 shadow-lg"
                  enableTilt={false}
                >
                  {/* Validation disclosure header */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 pb-3 border-b border-white/[0.08]">
                    <div className="flex flex-col gap-0.5">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-sm text-white">
                          Patch for {activePatch.package}
                        </span>
                        {activePatch.change_type && (
                          <span className="font-mono text-[9px] px-1.5 py-0.5 rounded bg-white/10 text-white uppercase border border-white/15">
                            {activePatch.change_type}
                          </span>
                        )}
                      </div>
                      <span className="font-sans text-xs text-[#A1A1AA]">
                        {activePatch.change_description || "Call-site automated AST rewrite"}
                      </span>
                    </div>

                    {activePatch.pr_url && (
                      <Link
                        href={activePatch.pr_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-mono text-xs font-semibold px-3 py-1.5 rounded-lg bg-white text-black hover:bg-white/90 transition-all flex items-center gap-1.5 self-start sm:self-auto shadow-sm"
                      >
                        <span>Inspect Pull Request</span>
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                        </svg>
                      </Link>
                    )}
                  </div>

                  {/* Verification Run Metrics */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 font-mono text-xs">
                    <div className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.06] flex flex-col gap-1">
                      <span className="text-[10px] text-[#71717A] uppercase">Verification Mode</span>
                      <span className="font-bold text-white">
                        {activePatch.verification_mode === "full" ? "Isolated Sandbox (CI)" : "Structural AST Only"}
                      </span>
                    </div>

                    <div className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.06] flex flex-col gap-1">
                      <span className="text-[10px] text-[#71717A] uppercase">Test Suite Gate</span>
                      <span className="font-bold text-white flex items-center gap-1.5">
                        {activePatch.tests_passed === true ? (
                          <>
                            <svg className="w-3.5 h-3.5 text-emerald-400 stroke-current" viewBox="0 0 24 24" fill="none" strokeWidth="2.5" aria-hidden="true">
                              <polyline points="20 6 9 17 4 12" />
                            </svg>
                            <span className="text-emerald-400">Passing (100%)</span>
                          </>
                        ) : activePatch.tests_passed === false ? (
                          <>
                            <svg className="w-3.5 h-3.5 text-rose-400 stroke-current" viewBox="0 0 24 24" fill="none" strokeWidth="2.5" aria-hidden="true">
                              <line x1="18" y1="6" x2="6" y2="18" />
                              <line x1="6" y1="6" x2="18" y2="18" />
                            </svg>
                            <span className="text-rose-400">Failed</span>
                          </>
                        ) : (
                          <span className="text-[#71717A]">&mdash; Bypassed / None</span>
                        )}
                      </span>
                    </div>

                    <div className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.06] flex flex-col gap-1">
                      <span className="text-[10px] text-[#71717A] uppercase">Typecheck Gate</span>
                      <span className="font-bold text-white flex items-center gap-1.5">
                        {activePatch.typecheck_passed === true ? (
                          <>
                            <svg className="w-3.5 h-3.5 text-emerald-400 stroke-current" viewBox="0 0 24 24" fill="none" strokeWidth="2.5" aria-hidden="true">
                              <polyline points="20 6 9 17 4 12" />
                            </svg>
                            <span className="text-emerald-400">Passing</span>
                          </>
                        ) : activePatch.typecheck_passed === false ? (
                          <>
                            <svg className="w-3.5 h-3.5 text-rose-400 stroke-current" viewBox="0 0 24 24" fill="none" strokeWidth="2.5" aria-hidden="true">
                              <line x1="18" y1="6" x2="6" y2="18" />
                              <line x1="6" y1="6" x2="18" y2="18" />
                            </svg>
                            <span className="text-rose-400">Failed</span>
                          </>
                        ) : (
                          <span className="text-[#71717A]">&mdash; Bypassed / None</span>
                        )}
                      </span>
                    </div>
                  </div>

                  {/* Diff Viewer */}
                  {activePatch.diff ? (
                    <div className="flex flex-col gap-1.5">
                      <span className="font-mono text-[11px] text-[#71717A] uppercase tracking-wider">
                        Synthesized Unified Diff
                      </span>
                      <DiffViewer
                        diff={activePatch.diff}
                        filename={activePatch.package}
                        animated={false}
                      />
                    </div>
                  ) : (
                    <div className="p-4 rounded-lg bg-white/[0.02] border border-white/10 text-center font-mono text-xs text-[#71717A]">
                      Diff recorded in GitHub Pull Request.
                    </div>
                  )}
                </SpotlightCard>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Gemini 2.5 Flash Architecture & Risk Radar */}
      <SpotlightCard
        spotlightColor="rgba(255, 255, 255, 0.08)"
        className="p-5 bg-black/70 backdrop-blur-xl border border-white/15 relative overflow-hidden flex flex-col gap-4 rounded-xl shadow-lg"
        enableTilt={false}
      >
        <BorderBeam size={220} duration={10} colorFrom="#FFFFFF" colorTo="rgba(255, 255, 255, 0.15)" />

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/[0.06] pb-3 relative z-10">
          <div className="flex items-center gap-2.5">
            <div className="w-6 h-6 rounded bg-white/10 border border-white/20 flex items-center justify-center font-mono text-[10px] font-bold text-white">
              AI
            </div>
            <div>
              <h2 className="font-mono font-semibold text-sm text-white tracking-tight">
                Gemini 2.5 Flash Architecture Radar
              </h2>
            </div>
          </div>

          <button
            onClick={handleRunGeminiExplain}
            disabled={isLoadingAi}
            className="font-mono text-xs font-semibold px-3.5 py-1.5 rounded-lg bg-white text-black hover:bg-white/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-1.5 self-start sm:self-auto shadow-sm cursor-pointer"
          >
            {isLoadingAi ? (
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full border-2 border-black/30 border-t-black animate-spin" />
                <span>Analyzing AST…</span>
              </span>
            ) : (
              <>
                <span>Run Gemini Analysis</span>
                <span>→</span>
              </>
            )}
          </button>
        </div>

        {aiError && (
          <div className="p-3 rounded-lg bg-white/[0.04] border border-white/20 text-white font-mono text-xs mb-3">
            <span className="font-semibold text-white/90">Error:</span> {aiError}
          </div>
        )}

        {isLoadingAi && (
          <div
            role="status"
            aria-label="Running Gemini Analysis"
            className="p-8 rounded-xl border border-white/10 bg-black/60 relative overflow-hidden flex flex-col items-center justify-center text-center gap-3.5 my-2 animate-fade-in"
          >
            <div className="animate-terminal-scan" />
            <div className="relative w-16 h-16 flex items-center justify-center">
              <div className="absolute inset-0 rounded-full border border-white/10 animate-ping opacity-25" />
              <div className="absolute inset-2 rounded-full border border-white/20 animate-pulse" />
              <div className="absolute inset-0 rounded-full border border-dashed border-white/40 animate-spin [animation-duration:5s]" />
              <span className="w-2.5 h-2.5 rounded-full bg-white shadow-[0_0_10px_#FFFFFF]" />
            </div>
            <div className="flex flex-col items-center gap-1">
              <span className="font-mono text-xs text-white font-bold uppercase tracking-wider flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse shadow-[0_0_6px_#FFFFFF]" />
                Scanning AST Call Sites &amp; Breaking Changes
              </span>
              <span className="font-mono text-[11px] text-[#A1A1AA]">
                Gemini 2.5 Flash computing semantic impact, migration diffs, and blast radius…
              </span>
            </div>
          </div>
        )}

        {aiExplanation ? (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col gap-4 relative z-10 font-mono text-xs"
          >
            <div className="p-3.5 rounded-lg bg-white/[0.02] border border-white/10">
              <div className="text-[#71717A] uppercase text-[10px] tracking-wider mb-1">
                Executive Architecture Summary
              </div>
              <p className="font-sans text-xs text-white leading-relaxed">
                {aiExplanation.summary}
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="p-3 rounded-lg bg-black/60 border border-white/[0.06] flex flex-col gap-0.5">
                <span className="text-[#71717A] text-[10px] uppercase">Risk Score</span>
                <span className="text-xl font-bold text-white">{aiExplanation.risk_score}/100</span>
                <span className="text-[10px] text-[#A1A1AA]">
                  {aiExplanation.risk_score < 30 ? "Nominal (Low Risk)" : "Medium Volatility"}
                </span>
              </div>

              <div className="p-3 rounded-lg bg-black/60 border border-white/[0.06] flex flex-col gap-0.5 md:col-span-2">
                <span className="text-[#71717A] text-[10px] uppercase">Architecture Verdict</span>
                <span className="text-xs text-white font-medium mt-0.5 leading-relaxed">
                  {aiExplanation.architecture_verdict}
                </span>
              </div>
            </div>
          </motion.div>
        ) : !aiError ? (
          <div className="py-4 text-center text-[#71717A] font-mono text-xs relative z-10">
            Click &quot;Run Gemini Analysis&quot; to synthesize live architectural risk insights.
          </div>
        ) : null}
      </SpotlightCard>

      {/* Commit Stream & Dependencies */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <SpotlightCard
          spotlightColor="rgba(255, 255, 255, 0.05)"
          className="p-4 bg-black/60 backdrop-blur-xl border border-white/10 flex flex-col gap-2.5 rounded-xl"
          enableTilt={false}
        >
          <h3 className="font-mono font-semibold text-xs text-white uppercase tracking-wider">
            Tracked Dependencies
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {repo.dependencies && repo.dependencies.length > 0 ? (
              repo.dependencies.map((dep) => (
                <span
                  key={dep}
                  className="font-mono text-xs px-2 py-0.5 rounded bg-white/5 border border-white/10 text-[#A1A1AA]"
                >
                  {dep}
                </span>
              ))
            ) : (
              <span className="font-mono text-xs text-[#71717A]">
                Dependencies indexed via Tree-Sitter
              </span>
            )}
          </div>
        </SpotlightCard>

        <SpotlightCard
          spotlightColor="rgba(255, 255, 255, 0.05)"
          className="p-4 bg-black/60 backdrop-blur-xl border border-white/10 flex flex-col gap-2.5 rounded-xl"
          enableTilt={false}
        >
          <h3 className="font-mono font-semibold text-xs text-white uppercase tracking-wider">
            Verification Engine
          </h3>
          <div className="font-mono text-xs text-[#A1A1AA] flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <span>AST Scanner:</span>
              <span className="text-white font-medium">Tree-Sitter Parity (TS/Py)</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Candidate Generator:</span>
              <span className="text-white font-medium">Best-of-3 MiniMax Ranking</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Quality Gates:</span>
              <span className="text-white font-medium">
                {repo.requires_tests ? "Tests Required" : "Tests Optional"} •{" "}
                {repo.requires_typecheck ? "Typecheck Required" : "Typecheck Optional"}
              </span>
            </div>
          </div>
        </SpotlightCard>
      </div>
    </div>
  );
}

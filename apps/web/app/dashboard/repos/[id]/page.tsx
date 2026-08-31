"use client";

import React, { useState, useEffect, use } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "motion/react";
import SpotlightCard from "@/components/ui/SpotlightCard";
import BorderBeam from "@/components/ui/BorderBeam";
import CyberGridBackground from "@/components/ui/CyberGridBackground";
import Badge from "@/components/ui/Badge";
import DiffViewer from "@/components/dashboard/DiffViewer";
import type { RepoDetails, AIExplanation, RepoPatches } from "@/lib/api";

const SAMPLE_DIFF = `--- a/src/services/payment.ts
+++ b/src/services/payment.ts
@@ -12,2 +12,2 @@
- const client = new OpenAI({ apiKey: process.env.OPENAI_KEY });
- const res = await client.createCompletion({ model: "text-davinci-003", prompt });
+ const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
+ const res = await client.chat.completions.create({ model: "gpt-4o", messages: [{ role: "user", content: prompt }] });`;

export default function RepoDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const resolvedParams = use(params);
  const repoId = resolvedParams.id;

  const [repo, setRepo] = useState<RepoDetails | null>(null);
  const [aiExplanation, setAiExplanation] = useState<AIExplanation | null>(null);
  const [aiError, setAiError] = useState<string | null>(null);
  const [isLoadingAi, setIsLoadingAi] = useState(false);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    let timer: NodeJS.Timeout | null = null;
    let isMounted = true;

    async function loadData() {
      if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
      try {
        const { getRepoDetails } = await import("@/lib/api");
        const repoData = await getRepoDetails(repoId).catch(() => null);

        if (!isMounted) return;
        if (repoData) {
          setRepo(repoData);
          setNotFound(false);
        } else {
          setNotFound(true);
        }
      } catch {
        if (isMounted) {
          setNotFound(true);
        }
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

  if (!repo) {
    if (notFound) {
      return (
        <div className="flex flex-col items-center justify-center min-h-[50vh] gap-3 text-center">
          <div className="font-mono text-sm text-white font-semibold">Repository not connected</div>
          <div className="text-xs text-[#71717A] max-w-sm">
            This repository is not registered with the Telex GitHub App or has been uninstalled.
          </div>
          <Link
            href="/dashboard"
            className="mt-2 text-xs font-mono px-3 py-1.5 rounded bg-white/10 text-white border border-white/15 hover:bg-white/20 transition-all"
          >
            ← Back to Fleet Overview
          </Link>
        </div>
      );
    }

    return (
      <div className="flex items-center justify-center min-h-[50vh] text-[#71717A] font-mono text-sm">
        Loading repository telemetry…
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 relative z-10 max-w-7xl mx-auto w-full">
      {/* Background */}
      <CyberGridBackground />

      {/* Clean Navigation Breadcrumb & Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 font-mono text-xs text-[#71717A]">
            <Link href="/dashboard" className="hover:text-white transition-colors">
              Fleet
            </Link>
            <span className="text-[#3F3F46]">/</span>
            <span className="text-white font-medium">{repo.full_name}</span>
          </div>

          <div className="flex items-center gap-3">
            <h1 className="font-mono font-bold text-xl sm:text-2xl text-white tracking-tight">
              {repo.full_name}
            </h1>
            <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-white/10 text-[#A1A1AA] border border-white/15">
              {repo.default_branch}
            </span>
          </div>

          <p className="font-sans text-xs text-[#71717A] max-w-2xl">
            {repo.description}
          </p>
        </div>

        {/* GitHub link button */}
        {repo.github_url && (
          <Link
            href={repo.github_url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-mono text-xs px-3.5 py-1.5 rounded-lg border border-white/15 bg-white/[0.04] text-white hover:bg-white hover:text-black transition-all flex items-center gap-1.5 self-start sm:self-center shadow-sm"
          >
            <span>GitHub Repository</span>
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </Link>
        )}
      </div>

      {/* Gemini 2.5 Flash AI Intelligence Console */}
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
                Gemini 2.5 Flash Architecture & Risk Radar
              </h2>
            </div>
          </div>

          <button
            onClick={handleRunGeminiExplain}
            disabled={isLoadingAi}
            className="font-mono text-xs font-semibold px-3.5 py-1.5 rounded-lg bg-white text-black hover:bg-white/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-1.5 self-start sm:self-auto shadow-sm"
          >
            {isLoadingAi ? (
              <span>Analyzing telemetry…</span>
            ) : (
              <>
                <span>Run Gemini AI Analysis</span>
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

            {aiExplanation.commit_insights.length > 0 && (
              <div className="flex flex-col gap-1.5">
                <span className="text-[#71717A] text-[10px] uppercase tracking-wider">
                  Commit-Level Insights
                </span>
                <div className="flex flex-col gap-1.5">
                  {aiExplanation.commit_insights.map((ins, i) => (
                    <div
                      key={i}
                      className="p-2.5 rounded bg-black/50 border border-white/[0.04] flex items-center justify-between gap-3 text-xs"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="bg-white/10 px-1.5 py-0.2 rounded text-white font-bold text-[11px]">
                          {ins.hash}
                        </span>
                        <span className="text-white truncate text-xs">{ins.impact}</span>
                      </div>
                      <span className="font-bold text-[10px] px-1.5 py-0.2 rounded bg-white/10 text-white border border-white/20 flex-shrink-0">
                        {ins.risk_level} RISK
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        ) : !aiError ? (
          <div className="py-4 text-center text-[#71717A] font-mono text-xs relative z-10">
            Click &quot;Run Gemini AI Analysis&quot; to synthesize live architectural risk insights.
          </div>
        ) : null}
      </SpotlightCard>

      {/* Streamlined Live Commit Timeline */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 className="font-mono font-semibold text-sm text-white tracking-tight">
            Recent Commit Stream
          </h2>
          <span className="font-mono text-xs text-[#71717A]">
            {repo.commits.length} recorded
          </span>
        </div>

        <div className="flex flex-col gap-2">
          {repo.commits.map((c, i) => (
            <div
              key={c.hash || i}
              className="p-3.5 rounded-xl border border-white/[0.08] bg-black/60 backdrop-blur-xl flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 hover:border-white/20 transition-colors"
            >
              <div className="flex items-center gap-3 min-w-0">
                <span className="font-mono text-xs font-bold text-white bg-white/10 px-2 py-1 rounded border border-white/10">
                  {c.short_hash}
                </span>
                <span className="font-sans text-xs text-white font-medium truncate">
                  {c.message}
                </span>
              </div>
              <div className="flex items-center gap-3 text-xs text-[#71717A] font-mono flex-shrink-0 self-end sm:self-auto">
                <span className="text-[#A1A1AA]">by {c.author}</span>
                <span>•</span>
                <span>{c.relative_time || c.date}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Compact Dependencies & Verification Grid */}
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
            {repo.dependencies?.map((dep) => (
              <span
                key={dep}
                className="font-mono text-xs px-2 py-0.5 rounded bg-white/5 border border-white/10 text-[#A1A1AA]"
              >
                {dep}
              </span>
            ))}
          </div>
        </SpotlightCard>

        <SpotlightCard
          spotlightColor="rgba(255, 255, 255, 0.05)"
          className="p-4 bg-black/60 backdrop-blur-xl border border-white/10 flex flex-col gap-2.5 rounded-xl"
          enableTilt={false}
        >
          <h3 className="font-mono font-semibold text-xs text-white uppercase tracking-wider">
            Verification Pipeline
          </h3>
          <div className="font-mono text-xs text-[#A1A1AA] flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <span>AST Parser:</span>
              <span className="text-white font-medium">Tree-sitter Ready</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Verification Sandbox:</span>
              <span className="text-white font-medium">Isolated Pytest Runner</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Status:</span>
              <Badge status="patched" />
            </div>
          </div>
        </SpotlightCard>
      </div>

      {/* Verified Diff Inspection */}
      <div className="flex flex-col gap-2 pt-2">
        <h3 className="font-mono font-semibold text-xs text-[#71717A] uppercase tracking-wider">
          Latest Verified Patch Diff (Example Reference)
        </h3>
        <DiffViewer diff={SAMPLE_DIFF} filename="services/payment_service.ts" animated={false} />
      </div>
    </div>
  );
}

"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "motion/react";
import SpotlightCard from "@/components/ui/SpotlightCard";
import CyberGridBackground from "@/components/ui/CyberGridBackground";
import {
  CyberSkeleton,
  CyberSkeletonMetric,
  CyberSkeletonRepo,
} from "@/components/ui/CyberSkeleton";
import type { Repo, Stats } from "@/lib/api";

export default function DashboardOverview() {
  const [repos, setRepos] = useState<(Repo & { category?: string })[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncNotice, setSyncNotice] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"personal" | "benchmark">("personal");

  const githubInstallUrl = `https://github.com/apps/${
    process.env.NEXT_PUBLIC_GITHUB_APP_NAME || "telex-agent-dev"
  }/installations/new`;

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      const { syncRepos, getStats } = await import("@/lib/api");
      const [reposRes, statsRes] = await Promise.allSettled([
        syncRepos(activeTab === "benchmark"),
        getStats(),
      ]);
      if (reposRes.status === "fulfilled" && reposRes.value) {
        setRepos(reposRes.value as (Repo & { category?: string })[]);
        const count = reposRes.value.filter((r) => (r as any).category !== "benchmark").length;
        setSyncNotice(`Synced ${count} personal repositories from GitHub App`);
        setTimeout(() => setSyncNotice(null), 4000);
      }
      if (statsRes.status === "fulfilled") {
        setStats(statsRes.value);
      }
    } catch (err: any) {
      setSyncNotice(`Sync failed: ${err?.message || "Could not connect to API"}`);
      setTimeout(() => setSyncNotice(null), 5000);
    } finally {
      setIsSyncing(false);
    }
  };

  const switchTab = (tab: "personal" | "benchmark") => {
    setActiveTab(tab);
  };

  const loadData = useCallback(async (forceSync: boolean = false) => {
    try {
      const { getRepos, getStats } = await import("@/lib/api");
      const [reposData, statsData] = await Promise.allSettled([
        getRepos(forceSync, activeTab === "benchmark"),
        getStats(),
      ]);

      if (reposData.status === "fulfilled") {
        setRepos((reposData.value || []) as (Repo & { category?: string })[]);
        setApiError(null);
      } else {
        setApiError("Unable to fetch repository telemetry from API backend.");
      }

      if (statsData.status === "fulfilled") {
        setStats(statsData.value);
      }
    } catch (err: any) {
      setApiError(err?.message || "Failed to connect to API backend.");
    } finally {
      setIsLoading(false);
    }
  }, [activeTab]);

  useEffect(() => {
    loadData(true);
    const timer = setInterval(() => loadData(false), 8000);

    const onFocus = () => loadData(true);
    window.addEventListener("focus", onFocus);

    return () => {
      clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, [loadData]);

  const displayedRepos = repos.filter((r) => {
    const isBenchmark = r.category === "benchmark";
    return activeTab === "benchmark" ? isBenchmark : !isBenchmark;
  });

  const totalPatches = stats?.patches_generated ?? repos.reduce((acc, r) => acc + (r.patch_count || 0), 0);
  const totalPrs = stats ? stats.prs_opened : 0;
  const mergeRateText = stats ? `${Math.round(stats.merge_rate * 100)}%` : "—";

  return (
    <div className="flex flex-col gap-6 relative z-10 max-w-7xl mx-auto w-full">
      {/* Background */}
      <CyberGridBackground />

      {/* Clean Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] tracking-wider text-[#A1A1AA] uppercase font-semibold">
              Autonomous Self-Healing
            </span>
            <span className="text-[#3F3F46]">/</span>
            <span className="font-mono text-[10px] text-white">System Radar</span>
          </div>
          <h1 className="font-mono font-bold text-xl sm:text-2xl text-white tracking-tight">
            Fleet Overview
          </h1>
          <p className="font-sans text-xs text-[#71717A]">
            Autonomous AST scanning, isolated sandbox verification, and automated PR delivery.
          </p>
        </div>

        {/* Header Actions */}
        <div className="flex items-center gap-3 self-start sm:self-center">
          <button
            onClick={handleSync}
            disabled={isSyncing}
            className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg border border-white/20 bg-white/[0.04] text-white hover:bg-white/[0.08] hover:border-white font-mono text-xs transition-all active:scale-[0.98] cursor-pointer"
          >
            <svg
              className={`w-3.5 h-3.5 ${isSyncing ? "animate-spin text-white" : "text-[#A1A1AA]"}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <span>{isSyncing ? "Syncing..." : "Sync Repos"}</span>
          </button>

          <a
            href={githubInstallUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-white text-black font-mono font-semibold text-xs transition-all hover:bg-white/90 hover:shadow-[0_0_15px_rgba(255,255,255,0.2)] active:scale-[0.98]"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            <span>Connect Repository</span>
          </a>

          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/[0.04] border border-white/10">
            <span className="relative flex h-1.5 w-1.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-white opacity-75" />
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-white shadow-[0_0_6px_#FFFFFF]" />
            </span>
            <span className="font-mono text-[11px] text-white font-medium">
              Live GitHub Stream
            </span>
          </div>
        </div>
      </div>

      {syncNotice && (
        <motion.div
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          className="px-4 py-2.5 rounded-xl bg-white/[0.08] border border-white/20 text-white font-mono text-xs flex items-center gap-2.5"
        >
          <span className="w-2 h-2 rounded-full bg-white animate-pulse shadow-[0_0_8px_#FFFFFF]" />
          <span>{syncNotice}</span>
        </motion.div>
      )}

      {/* State 1: Loading Skeleton */}
      {isLoading ? (
        <div className="flex flex-col gap-6 animate-fade-in" role="status" aria-label="Loading dashboard telemetry">
          <CyberSkeletonMetric />

          {/* Recent Breaking Changes Skeleton */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <CyberSkeleton className="w-44 h-4 bg-white/[0.06]" />
              <CyberSkeleton className="w-24 h-4 bg-white/[0.04]" />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {[...Array(3)].map((_, i) => (
                <div
                  key={i}
                  className="p-3.5 bg-black/60 border border-white/10 rounded-xl flex flex-col gap-2.5 animate-shimmer"
                >
                  <div className="flex items-center justify-between">
                    <CyberSkeleton className="w-24 h-4 bg-white/[0.08]" />
                    <CyberSkeleton className="w-16 h-4 rounded bg-white/[0.05]" />
                  </div>
                  <CyberSkeleton className="w-full h-3 bg-white/[0.04]" />
                  <div className="pt-2 border-t border-white/[0.06] flex justify-between">
                    <CyberSkeleton className="w-24 h-2.5 bg-white/[0.04]" />
                    <CyberSkeleton className="w-16 h-2.5 bg-white/[0.03]" />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Fleet Controls & Monitored Repositories Skeleton */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <CyberSkeleton className="w-32 h-4 bg-white/[0.06]" />
              <CyberSkeleton className="w-20 h-4 bg-white/[0.04]" />
            </div>
            <CyberSkeletonRepo />
            <CyberSkeletonRepo />
            <CyberSkeletonRepo />
          </div>
        </div>
      ) : apiError && repos.length === 0 ? (
        <SpotlightCard
          spotlightColor="rgba(255, 255, 255, 0.08)"
          className="p-8 sm:p-12 bg-black/70 backdrop-blur-xl border border-white/15 rounded-2xl flex flex-col items-center text-center gap-4 shadow-2xl"
          enableTilt={false}
        >
          <div className="w-14 h-14 rounded-2xl bg-white/5 border border-white/15 flex items-center justify-center text-white">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
            </svg>
          </div>
          <div className="flex flex-col gap-1 max-w-md">
            <h2 className="font-mono font-bold text-lg text-white">Unable to Load Telemetry</h2>
            <p className="font-sans text-xs text-[#A1A1AA]">{apiError}</p>
          </div>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 rounded-lg bg-white text-black font-mono font-semibold text-xs hover:bg-white/90 transition-all"
          >
            Retry Connection
          </button>
        </SpotlightCard>
      ) : displayedRepos.length === 0 ? (
        /* State 2: Empty State (0 repos in current view) */
        <SpotlightCard
          spotlightColor="rgba(255, 255, 255, 0.08)"
          className="p-8 sm:p-12 bg-black/70 backdrop-blur-xl border border-white/15 rounded-2xl flex flex-col items-center text-center gap-6 shadow-2xl"
          enableTilt={false}
        >
          <div className="w-16 h-16 rounded-2xl bg-white/5 border border-white/15 flex items-center justify-center">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-white">
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244" />
            </svg>
          </div>

          {/* Interactive tab switcher so user can toggle between tabs even when empty */}
          <div className="flex items-center p-1 rounded-lg bg-white/5 border border-white/10">
            <button
              onClick={() => switchTab("personal")}
              className={`px-3 py-1 rounded-md font-mono text-xs font-medium transition-all ${
                activeTab === "personal"
                  ? "bg-white text-black shadow-sm"
                  : "text-[#71717A] hover:text-white"
              }`}
            >
              My Repositories
            </button>
            <button
              onClick={() => switchTab("benchmark")}
              className={`px-3 py-1 rounded-md font-mono text-xs font-medium transition-all ${
                activeTab === "benchmark"
                  ? "bg-white text-black shadow-sm"
                  : "text-[#71717A] hover:text-white"
              }`}
            >
              Industry Benchmarks
            </button>
          </div>

          <div className="flex flex-col gap-2 max-w-lg">
            <h2 className="font-mono font-bold text-xl text-white">
              {activeTab === "benchmark"
                ? "No benchmark repositories found"
                : "Connect your first repository"}
            </h2>
            <p className="font-sans text-xs sm:text-sm text-[#A1A1AA] leading-relaxed">
              {activeTab === "benchmark"
                ? "No benchmark targets are currently available. Switch to My Repositories to view your active codebases."
                : "Install the Telex GitHub App to monitor your repositories. Whenever an upstream dependency ships a breaking release, Telex parses call sites with Tree-Sitter, generates verified fixes, and opens ready-to-merge pull requests."}
            </p>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-3">
            {activeTab === "personal" ? (
              <a
                href={githubInstallUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-white text-black font-mono font-bold text-xs hover:bg-white/90 transition-all shadow-lg hover:shadow-white/10"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
                <span>Connect Repository via GitHub App</span>
              </a>
            ) : (
              <button
                onClick={() => switchTab("personal")}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-white text-black font-mono font-bold text-xs hover:bg-white/90 transition-all shadow-lg hover:shadow-white/10"
              >
                <span>← View My Repositories</span>
              </button>
            )}
            <Link
              href="/dashboard/activity"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-white/20 bg-white/5 text-white font-mono text-xs hover:bg-white/10 transition-colors"
            >
              <span>View Global Activity Feed →</span>
            </Link>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4 border-t border-white/10 w-full max-w-2xl text-left">
            <div className="p-3.5 rounded-lg bg-white/[0.02] border border-white/5 flex flex-col gap-1">
              <span className="font-mono text-[11px] font-semibold text-white">1. AST Call-Site Mapping</span>
              <span className="text-[11px] text-[#71717A]">Extracts exact imported symbols across TypeScript and Python repos.</span>
            </div>
            <div className="p-3.5 rounded-lg bg-white/[0.02] border border-white/5 flex flex-col gap-1">
              <span className="font-mono text-[11px] font-semibold text-white">2. Isolated Sandbox Gate</span>
              <span className="text-[11px] text-[#71717A]">Ephemeral verification branches run real test suites and typechecks before PR.</span>
            </div>
            <div className="p-3.5 rounded-lg bg-white/[0.02] border border-white/5 flex flex-col gap-1">
              <span className="font-mono text-[11px] font-semibold text-white">3. Honest Disclosure</span>
              <span className="text-[11px] text-[#71717A]">Every PR transparently reports whether validation was full sandbox or structural.</span>
            </div>
          </div>
        </SpotlightCard>
      ) : (
        /* State 3: Populated State */
        <>
          {apiError && (
            <div className="flex items-center justify-between p-3.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 font-mono text-xs">
              <div className="flex items-center gap-2 min-w-0">
                <svg
                  className="w-4 h-4 stroke-current flex-shrink-0"
                  viewBox="0 0 24 24"
                  fill="none"
                  strokeWidth="2"
                  aria-hidden="true"
                >
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                <span className="truncate">{apiError} (Showing cached telemetry)</span>
              </div>
              <button
                onClick={() => loadData(true)}
                className="px-3 py-1 rounded bg-red-500/20 hover:bg-red-500/30 text-red-200 transition-colors cursor-pointer flex-shrink-0 ml-3"
              >
                Retry
              </button>
            </div>
          )}
          {/* Metric Strip */}
          <div className="grid grid-cols-2 md:grid-cols-4 rounded-xl border border-white/10 bg-black/60 backdrop-blur-xl divide-y md:divide-y-0 md:divide-x divide-white/[0.08] shadow-lg">
            <div className="p-4 flex flex-col gap-0.5">
              <span className="font-mono text-[11px] text-[#71717A] uppercase tracking-wider">
                Active Targets
              </span>
              <div className="flex items-baseline gap-1.5">
                <span className="font-mono font-bold text-2xl text-white">{displayedRepos.length}</span>
                <span className="font-mono text-[10px] text-[#A1A1AA]">monitored</span>
              </div>
            </div>

            <div className="p-4 flex flex-col gap-0.5">
              <span className="font-mono text-[11px] text-[#71717A] uppercase tracking-wider">
                Verified PRs
              </span>
              <div className="flex items-baseline gap-1.5">
                <span className="font-mono font-bold text-2xl text-white">{totalPrs}</span>
                <span className="font-mono text-[10px] text-[#A1A1AA]">delivered</span>
              </div>
            </div>

            <div className="p-4 flex flex-col gap-0.5">
              <span className="font-mono text-[11px] text-[#71717A] uppercase tracking-wider">
                Synthesized Patches
              </span>
              <div className="flex items-baseline gap-1.5">
                <span className="font-mono font-bold text-2xl text-white">{totalPatches}</span>
                <span className="font-mono text-[10px] text-[#A1A1AA]">healed</span>
              </div>
            </div>

            <div className="p-4 flex flex-col gap-0.5">
              <span className="font-mono text-[11px] text-[#71717A] uppercase tracking-wider">
                Merge Success
              </span>
              <div className="flex items-baseline gap-1.5">
                <span className="font-mono font-bold text-2xl text-white">{mergeRateText}</span>
                <span className="font-mono text-[10px] text-white/70">acceptance</span>
              </div>
            </div>
          </div>

          {/* Recent Detected Changes (Last 5) */}
          {stats?.recent_changes && stats.recent_changes.length > 0 && (
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-semibold text-sm text-white">
                    Upstream Breaking Changes
                  </span>
                  <span className="font-mono text-[10px] px-2 py-0.5 rounded-full bg-white/10 text-[#A1A1AA] border border-white/15">
                    Latest {stats.recent_changes.length}
                  </span>
                </div>
                <Link
                  href="/dashboard/activity"
                  className="font-mono text-xs text-[#A1A1AA] hover:text-white transition-colors"
                >
                  View Activity Feed →
                </Link>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {stats.recent_changes.map((change) => (
                  <SpotlightCard
                    key={change.id}
                    spotlightColor="rgba(255, 255, 255, 0.05)"
                    className="p-3.5 bg-black/60 backdrop-blur-xl border border-white/10 flex flex-col justify-between gap-2.5 rounded-xl hover:border-white/20 transition-all"
                    enableTilt={false}
                  >
                    <div className="flex flex-col gap-1.5">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono text-xs font-bold text-white truncate">
                          {change.symbol_old}
                        </span>
                        <span className="font-mono text-[9px] px-1.5 py-0.5 rounded bg-white/10 text-white uppercase border border-white/15 flex-shrink-0">
                          {change.change_type}
                        </span>
                      </div>
                      <p className="font-sans text-[11px] text-[#A1A1AA] line-clamp-2">
                        {change.description}
                      </p>
                    </div>

                    <div className="flex items-center justify-between pt-2 border-t border-white/[0.06] font-mono text-[10px] text-[#71717A]">
                      {change.symbol_new ? (
                        <span className="text-white/80">→ {change.symbol_new}</span>
                      ) : (
                        <span>Call site affected</span>
                      )}
                      <span>{new Date(change.created_at).toLocaleDateString()}</span>
                    </div>
                  </SpotlightCard>
                ))}
              </div>
            </div>
          )}

          {/* Fleet Controls & Monitored Repositories */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2">
            <div className="flex items-center gap-2">
              <span className="font-mono font-semibold text-sm text-white">Connected Fleet</span>
              <span className="font-mono text-[10px] px-2 py-0.5 rounded-full bg-white/10 text-[#A1A1AA] border border-white/15">
                {displayedRepos.length} in view
              </span>
            </div>

            <div className="flex items-center gap-2.5 self-start sm:self-auto">
              <div className="inline-flex p-0.5 rounded-lg bg-white/[0.04] border border-white/10 backdrop-blur-md">
                <button
                  onClick={() => switchTab("personal")}
                  className={`px-3 py-1 rounded-md font-mono text-xs font-medium transition-all ${
                    activeTab === "personal"
                      ? "bg-white text-black shadow-sm"
                      : "text-[#71717A] hover:text-white"
                  }`}
                >
                  My Repositories
                </button>
                <button
                  onClick={() => switchTab("benchmark")}
                  className={`px-3 py-1 rounded-md font-mono text-xs font-medium transition-all ${
                    activeTab === "benchmark"
                      ? "bg-white text-black shadow-sm"
                      : "text-[#71717A] hover:text-white"
                  }`}
                >
                  Industry Benchmarks
                </button>
              </div>

              <Link
                href="/dashboard/repos"
                className="hidden sm:inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-white/20 bg-white/5 hover:bg-white/10 text-white font-mono text-xs font-medium transition-colors"
              >
                <span>Manage Policies →</span>
              </Link>
            </div>
          </div>

          {/* Repository Cards */}
          <div className="flex flex-col gap-3">
            <AnimatePresence mode="popLayout">
              {displayedRepos.map((repo) => (
                <motion.div
                  key={repo.id}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ duration: 0.15 }}
                >
                  <SpotlightCard
                    spotlightColor="rgba(255, 255, 255, 0.05)"
                    className="p-4 sm:p-5 bg-black/70 backdrop-blur-xl border border-white/10 hover:border-white/25 transition-all flex flex-col gap-3 rounded-xl"
                    enableTilt={false}
                  >
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-2.5">
                      <div className="flex items-center gap-2.5 flex-wrap min-w-0">
                        <div className="w-7 h-7 rounded bg-white/10 border border-white/20 flex items-center justify-center font-mono text-xs font-bold text-white flex-shrink-0">
                          {repo.name?.slice(0, 2).toUpperCase() || "RX"}
                        </div>

                        <Link
                          href={`/dashboard/repos/${repo.id}`}
                          className="font-mono font-bold text-sm sm:text-base text-white hover:underline transition-colors truncate"
                        >
                          {repo.full_name}
                        </Link>

                        <span className="font-mono text-[10px] px-1.5 py-0.2 rounded bg-white/5 text-[#71717A] border border-white/10">
                          {repo.default_branch}
                        </span>

                        <div className="hidden sm:flex items-center gap-1.5">
                          {repo.languages?.slice(0, 2).map((lang) => (
                            <span
                              key={lang}
                              className="font-mono text-[10px] px-1.5 py-0.2 rounded bg-white/[0.03] text-[#71717A]"
                            >
                              {lang}
                            </span>
                          ))}
                        </div>
                      </div>

                      <div className="flex items-center gap-2 self-start md:self-auto flex-shrink-0">
                        <span className="font-mono text-[11px] text-[#71717A] mr-1 hidden sm:inline">
                          <span className="text-white font-medium">{repo.patch_count}</span> patches
                        </span>

                        {repo.github_url && (
                          <Link
                            href={repo.github_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-mono text-xs px-2.5 py-1 rounded border border-white/15 text-[#A1A1AA] hover:text-white hover:border-white/30 transition-all flex items-center gap-1"
                          >
                            <span>GitHub</span>
                            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                            </svg>
                          </Link>
                        )}

                        <Link
                          href={`/dashboard/repos/${repo.id}`}
                          className="font-mono text-xs font-semibold px-3 py-1 rounded bg-white text-black hover:bg-white/90 transition-all flex items-center gap-1 shadow-sm"
                        >
                          <span>Inspect →</span>
                        </Link>
                      </div>
                    </div>

                    {repo.description && (
                      <p className="font-sans text-xs text-[#A1A1AA] line-clamp-1">
                        {repo.description}
                      </p>
                    )}

                    {repo.last_commit && (
                      <div className="flex items-center gap-2 font-mono text-[11px] text-[#71717A] pt-1 border-t border-white/[0.04]">
                        <span className="text-white font-medium bg-white/10 px-1 py-0.2 rounded border border-white/15 flex-shrink-0">
                          {repo.last_commit.short_hash}
                        </span>
                        <span className="text-white/90 truncate">
                          {repo.last_commit.message}
                        </span>
                        <span className="text-[#52525B] flex-shrink-0 hidden md:inline">
                          • by <span className="text-[#A1A1AA]">{repo.last_commit.author}</span> ({repo.last_commit.relative_time})
                        </span>
                      </div>
                    )}
                  </SpotlightCard>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </>
      )}
    </div>
  );
}

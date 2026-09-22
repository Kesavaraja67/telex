"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "motion/react";
import SpotlightCard from "@/components/ui/SpotlightCard";
import CyberGridBackground from "@/components/ui/CyberGridBackground";
import { CyberSkeletonRepo } from "@/components/ui/CyberSkeleton";
import type { Repo } from "@/lib/api";

export default function ReposPage() {
  const [repos, setRepos] = useState<Repo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncNotice, setSyncNotice] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [toggleErrors, setToggleErrors] = useState<Record<string, string>>({});

  const githubInstallUrl = `https://github.com/apps/${
    process.env.NEXT_PUBLIC_GITHUB_APP_NAME || "telex-agent-dev"
  }/installations/new`;

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      const { syncRepos } = await import("@/lib/api");
      const updated = await syncRepos(false);
      if (updated) {
        const connected = updated.filter((r) => (r as any).category !== "benchmark");
        setRepos(connected);
        setSyncNotice(`Synced ${connected.length} personal repositories from GitHub App`);
        setTimeout(() => setSyncNotice(null), 4000);
      }
    } catch (err: any) {
      setSyncNotice(`Sync failed: ${err?.message || "Could not connect to API"}`);
      setTimeout(() => setSyncNotice(null), 5000);
    } finally {
      setIsSyncing(false);
    }
  };

  const loadRepos = useCallback(async (forceSync: boolean = false) => {
    try {
      const { getRepos } = await import("@/lib/api");
      const data = await getRepos(forceSync, false);
      if (data) {
        const connected = data.filter((r) => (r as any).category !== "benchmark");
        setRepos(connected);
        setApiError(null);
      } else {
        setApiError("Unable to fetch repository telemetry.");
      }
    } catch (err: any) {
      setApiError(err?.message || "Failed to connect to API backend.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRepos(true);
    const timer = setInterval(() => loadRepos(false), 8000);

    const onFocus = () => loadRepos(true);
    window.addEventListener("focus", onFocus);

    return () => {
      clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, [loadRepos]);

  async function handleToggle(
    repoId: string,
    field: "requires_tests" | "requires_typecheck",
    currentValue: boolean
  ) {
    const newValue = !currentValue;
    setUpdatingId(`${repoId}-${field}`);

    // Clear previous error on retry
    setToggleErrors((prev) => {
      const next = { ...prev };
      delete next[repoId];
      return next;
    });

    // Optimistic update
    setRepos((prev) =>
      prev.map((r) => (r.id === repoId ? { ...r, [field]: newValue } : r))
    );

    try {
      const { updateRepoSettings } = await import("@/lib/api");
      await updateRepoSettings(repoId, { [field]: newValue });
    } catch (err: any) {
      // Revert on error and surface message
      setRepos((prev) =>
        prev.map((r) => (r.id === repoId ? { ...r, [field]: currentValue } : r))
      );
      setToggleErrors((prev) => ({
        ...prev,
        [repoId]: err?.message || "Failed to persist policy change. Check API authentication.",
      }));
    } finally {
      setUpdatingId(null);
    }
  }

  return (
    <div className="flex flex-col gap-6 relative z-10 max-w-7xl mx-auto w-full">
      <CyberGridBackground />

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <Link href="/dashboard" className="font-mono text-[10px] text-[#71717A] hover:text-white uppercase transition-colors">
              Fleet Overview
            </Link>
            <span className="text-[#3F3F46]">/</span>
            <span className="font-mono text-[10px] text-white">Repository Settings & Policies</span>
          </div>
          <h1 className="font-mono font-bold text-xl sm:text-2xl text-white tracking-tight">
            Connected Repositories
          </h1>
          <p className="font-sans text-xs text-[#71717A]">
            Configure isolated sandbox verification gates and quality policies per repository.
          </p>
        </div>

        {/* Action: Connect More Repos & Sync */}
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
            <span>Connect More Repositories</span>
          </a>
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
        <div className="flex flex-col gap-4 animate-fade-in" role="status" aria-label="Loading repositories">
          <CyberSkeletonRepo />
          <CyberSkeletonRepo />
          <CyberSkeletonRepo />
        </div>
      ) : apiError && repos.length === 0 ? (
        /* State: Telemetry Connection Failed */
        <SpotlightCard
          spotlightColor="rgba(255, 255, 255, 0.08)"
          className="p-8 sm:p-12 bg-black/70 backdrop-blur-xl border border-white/15 rounded-2xl flex flex-col items-center text-center gap-4 shadow-2xl"
          enableTilt={false}
        >
          <div className="w-14 h-14 rounded-2xl bg-white/5 border border-white/15 flex items-center justify-center text-rose-400">
            <svg
              className="w-6 h-6 stroke-current"
              viewBox="0 0 24 24"
              fill="none"
              strokeWidth="2"
              aria-hidden="true"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
          <div className="flex flex-col gap-1 max-w-md">
            <h2 className="font-mono font-bold text-lg text-white">
              Telemetry Connection Failed
            </h2>
            <p className="font-sans text-xs text-[#A1A1AA]">{apiError}</p>
          </div>
          <button
            onClick={() => {
              setIsLoading(true);
              setApiError(null);
              window.location.reload();
            }}
            className="px-4 py-2 rounded-lg bg-white text-black font-mono font-semibold text-xs hover:bg-white/90 transition-all cursor-pointer"
          >
            Retry Connection
          </button>
        </SpotlightCard>
      ) : repos.length === 0 ? (
        /* State 2: Empty State */
        <SpotlightCard
          spotlightColor="rgba(255, 255, 255, 0.08)"
          className="p-8 sm:p-12 bg-black/70 backdrop-blur-xl border border-white/15 rounded-2xl flex flex-col items-center text-center gap-5 shadow-2xl"
          enableTilt={false}
        >
          <div className="w-14 h-14 rounded-xl bg-white/5 border border-white/15 flex items-center justify-center">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-white">
              <rect width="18" height="18" x="3" y="3" rx="2" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 9h18M9 21V9" />
            </svg>
          </div>

          <div className="flex flex-col gap-1.5 max-w-md">
            <h2 className="font-mono font-bold text-lg text-white">
              No repositories connected yet
            </h2>
            <p className="font-sans text-xs text-[#A1A1AA] leading-relaxed">
              Install the Telex GitHub App to authorize repositories. Once connected, you can configure granular sandbox validation policies such as test suite gates and typechecking.
            </p>
          </div>

          <a
            href={githubInstallUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-white text-black font-mono font-bold text-xs hover:bg-white/90 transition-all shadow-lg hover:shadow-white/10"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            <span>Authorize GitHub Repositories</span>
          </a>
        </SpotlightCard>
      ) : (
        /* State 3: Populated State */
        <div className="flex flex-col gap-4">
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
                <span className="truncate">{apiError} (Showing cached repositories)</span>
              </div>
              <button
                onClick={() => loadRepos(true)}
                className="px-3 py-1 rounded bg-red-500/20 hover:bg-red-500/30 text-red-200 transition-colors cursor-pointer flex-shrink-0 ml-3"
              >
                Retry
              </button>
            </div>
          )}
          <div className="p-3.5 rounded-xl border border-white/10 bg-white/[0.02] flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs font-mono">
            <div className="flex items-center gap-2 text-[#A1A1AA]">
              <span className="text-white font-bold flex items-center gap-1.5">
                <svg className="w-3.5 h-3.5 text-blue-400 stroke-current" viewBox="0 0 24 24" fill="none" strokeWidth="2" aria-hidden="true">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M12 16v-4" />
                  <path d="M12 8h.01" />
                </svg>
                Quality Gate Rules:
              </span>
              <span>Enabling test or typecheck gates enforces isolated CI execution before any PR is created.</span>
            </div>
            <span className="text-[#71717A] text-[11px]">
              {repos.length} total repos configured
            </span>
          </div>

          <AnimatePresence mode="popLayout">
            {repos.map((repo) => (
              <motion.div
                key={repo.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.15 }}
              >
                <SpotlightCard
                  spotlightColor="rgba(255, 255, 255, 0.05)"
                  className="p-5 bg-black/70 backdrop-blur-xl border border-white/10 hover:border-white/20 transition-all rounded-xl flex flex-col gap-4"
                  enableTilt={false}
                >
                  {/* Repo Header */}
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded bg-white/10 border border-white/20 flex items-center justify-center font-mono text-xs font-bold text-white flex-shrink-0">
                        {repo.name?.slice(0, 2).toUpperCase() || "RX"}
                      </div>
                      <div className="flex flex-col">
                        <div className="flex items-center gap-2">
                          <Link
                            href={`/dashboard/repos/${repo.id}`}
                            className="font-mono font-bold text-base text-white hover:underline transition-colors"
                          >
                            {repo.full_name}
                          </Link>
                          <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-[#71717A] border border-white/10">
                            {repo.default_branch}
                          </span>
                        </div>
                        {repo.description && (
                          <p className="font-sans text-xs text-[#A1A1AA] line-clamp-1 mt-0.5">
                            {repo.description}
                          </p>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 self-start md:self-auto">
                      <Link
                        href={`/dashboard/repos/${repo.id}`}
                        className="font-mono text-xs px-3 py-1.5 rounded-lg border border-white/15 bg-white/5 text-white hover:bg-white hover:text-black transition-all flex items-center gap-1.5"
                      >
                        <span>View Patches</span>
                        <span>→</span>
                      </Link>
                    </div>
                  </div>

                  {/* Toggle Error Banner if mutation rejected */}
                  {toggleErrors[repo.id] && (
                    <div className="p-2.5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 font-mono text-xs flex items-center justify-between">
                      <span>{toggleErrors[repo.id]}</span>
                    </div>
                  )}

                  {/* Quality Gate Policy Toggles */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-3 border-t border-white/[0.06]">
                    {/* Toggle: requires_tests */}
                    <div className="p-3 rounded-lg bg-black/40 border border-white/[0.06] flex items-center justify-between gap-3">
                      <div className="flex flex-col gap-0.5">
                        <div className="flex items-center gap-1.5 font-mono text-xs font-semibold text-white">
                          <span>Require Passing Tests</span>
                          {repo.requires_tests && (
                            <span className="text-[9px] px-1 rounded bg-white/10 text-white font-mono">
                              ACTIVE
                            </span>
                          )}
                        </div>
                        <span className="font-sans text-[11px] text-[#71717A]">
                          Block auto-PRs if repo test suite fails in sandbox
                        </span>
                      </div>

                      <button
                        onClick={() =>
                          handleToggle(
                            repo.id,
                            "requires_tests",
                            Boolean(repo.requires_tests)
                          )
                        }
                        disabled={updatingId === `${repo.id}-requires_tests`}
                        className={`w-11 h-6 rounded-full transition-colors relative flex items-center p-0.5 cursor-pointer disabled:opacity-50 ${
                          repo.requires_tests ? "bg-white" : "bg-white/15"
                        }`}
                        aria-label="Toggle test requirement"
                      >
                        <motion.div
                          className={`w-5 h-5 rounded-full shadow-md ${
                            repo.requires_tests ? "bg-black" : "bg-white"
                          }`}
                          animate={{
                            x: repo.requires_tests ? 20 : 0,
                          }}
                          transition={{ type: "spring", stiffness: 500, damping: 30 }}
                        />
                      </button>
                    </div>

                    {/* Toggle: requires_typecheck */}
                    <div className="p-3 rounded-lg bg-black/40 border border-white/[0.06] flex items-center justify-between gap-3">
                      <div className="flex flex-col gap-0.5">
                        <div className="flex items-center gap-1.5 font-mono text-xs font-semibold text-white">
                          <span>Require Typecheck</span>
                          {repo.requires_typecheck && (
                            <span className="text-[9px] px-1 rounded bg-white/10 text-white font-mono">
                              ACTIVE
                            </span>
                          )}
                        </div>
                        <span className="font-sans text-[11px] text-[#71717A]">
                          Block auto-PRs if typechecker (tsc / mypy) fails
                        </span>
                      </div>

                      <button
                        onClick={() =>
                          handleToggle(
                            repo.id,
                            "requires_typecheck",
                            Boolean(repo.requires_typecheck)
                          )
                        }
                        disabled={updatingId === `${repo.id}-requires_typecheck`}
                        className={`w-11 h-6 rounded-full transition-colors relative flex items-center p-0.5 cursor-pointer disabled:opacity-50 ${
                          repo.requires_typecheck ? "bg-white" : "bg-white/15"
                        }`}
                        aria-label="Toggle typecheck requirement"
                      >
                        <motion.div
                          className={`w-5 h-5 rounded-full shadow-md ${
                            repo.requires_typecheck ? "bg-black" : "bg-white"
                          }`}
                          animate={{
                            x: repo.requires_typecheck ? 20 : 0,
                          }}
                          transition={{ type: "spring", stiffness: 500, damping: 30 }}
                        />
                      </button>
                    </div>
                  </div>
                </SpotlightCard>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}

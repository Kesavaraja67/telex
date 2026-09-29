"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "motion/react";
import SpotlightCard from "@/components/ui/SpotlightCard";
import CyberGridBackground from "@/components/ui/CyberGridBackground";
import { CyberSkeletonActivity } from "@/components/ui/CyberSkeleton";
import type { ActivityItem } from "@/lib/api";

export default function ActivityPage() {
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);

  const loadActivity = useCallback(async () => {
    try {
      const { getActivity } = await import("@/lib/api");
      const data = await getActivity();
      if (data?.activities) {
        setActivities(data.activities);
        setApiError(null);
      } else {
        setApiError("Unable to stream live event log.");
      }
    } catch (err: any) {
      setApiError(err?.message || "Failed to connect to telemetry backend.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadActivity();
    const timer = setInterval(loadActivity, 10000);
    return () => {
      clearInterval(timer);
    };
  }, [loadActivity]);

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
            <span className="font-mono text-[10px] text-white">Event Log</span>
          </div>
          <h1 className="font-mono font-bold text-xl sm:text-2xl text-white tracking-tight">
            Activity Feed
          </h1>
          <p className="font-sans text-xs text-[#71717A]">
            Reverse-chronological log of breaking changes detected, synthesized patches, and pull requests opened.
          </p>
        </div>

        <div className="badge-chip px-3 py-1.5 font-mono text-[11px] text-white font-medium flex items-center gap-2 self-start sm:self-center">
          <span className="led" data-state="ok" />
          <span>Live Stream Active</span>
        </div>
      </div>

      {/* State 1: Loading */}
      {isLoading ? (
        <div className="flex flex-col gap-3 animate-fade-in" role="status" aria-label="Streaming activity feed">
          <CyberSkeletonActivity />
          <CyberSkeletonActivity />
          <CyberSkeletonActivity />
          <CyberSkeletonActivity />
        </div>
      ) : apiError && activities.length === 0 ? (
        /* State: Stream Connection Interrupted */
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
              Event Stream Interrupted
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
            Reconnect Stream
          </button>
        </SpotlightCard>
      ) : activities.length === 0 ? (
        /* State 2: Empty State */
        <SpotlightCard
          spotlightColor="rgba(255, 255, 255, 0.08)"
          className="p-8 sm:p-12 bg-black/70 backdrop-blur-xl border border-white/15 rounded-2xl flex flex-col items-center text-center gap-5 shadow-2xl"
          enableTilt={false}
        >
          <div className="w-14 h-14 rounded-xl bg-white/5 border border-white/15 flex items-center justify-center text-white">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>

          <div className="flex flex-col gap-1.5 max-w-md">
            <h2 className="font-mono font-bold text-lg text-white">
              No activity recorded yet
            </h2>
            <p className="font-sans text-xs text-[#A1A1AA] leading-relaxed">
              Autonomous self-healing events will stream here in real time as breaking changes are detected, patches are generated, and pull requests are opened.
            </p>
          </div>

          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-white text-black font-mono font-semibold text-xs hover:bg-white/90 transition-all shadow-md"
          >
            <span>← Back to Fleet Overview</span>
          </Link>
        </SpotlightCard>
      ) : (
        /* State 3: Populated Feed */
        <div className="flex flex-col gap-2.5">
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
                <span className="truncate">{apiError} (Showing cached event log)</span>
              </div>
              <button
                onClick={() => loadActivity()}
                className="px-3 py-1 rounded bg-red-500/20 hover:bg-red-500/30 text-red-200 transition-colors cursor-pointer flex-shrink-0 ml-3"
              >
                Retry
              </button>
            </div>
          )}
          <AnimatePresence mode="popLayout">
            {activities.map((item) => (
              <motion.div
                key={item.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.15 }}
              >
                <div className="metal-bezel p-[2px] rounded-xl shadow-lg transition-all hover:brightness-105">
                  <div className="panel-inset p-4 rounded-[10px] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="flex items-start sm:items-center gap-3.5 min-w-0">
                      {/* Socketed type badge chip with dome LED */}
                      <div className="badge-chip px-2.5 py-1 text-[10px] font-mono font-bold flex items-center gap-1.5 flex-shrink-0 mt-0.5 sm:mt-0">
                        <span
                          className="led"
                          data-state={
                            item.type === "pull_request"
                              ? "ok"
                              : item.type === "patch"
                              ? "busy"
                              : "warn"
                          }
                        />
                        <span>
                          {item.type === "pull_request" ? "PR" : item.type === "patch" ? "FIX" : "EV"}
                        </span>
                      </div>

                      <div className="flex flex-col min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-mono text-xs font-bold text-white truncate label-embossed">
                            {item.title}
                          </span>
                          <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-[#A1A1AA] border border-white/10">
                            {item.repo_name}
                          </span>
                          {item.merged && (
                            <span className="font-mono text-[9px] px-1.5 py-0.5 rounded bg-white text-black font-bold">
                              MERGED
                            </span>
                          )}
                          {item.verification_mode && (
                            <span className="font-mono text-[9px] px-1.5 py-0.5 rounded bg-white/10 text-white border border-white/15">
                              {item.verification_mode === "full" ? "Sandbox Verified" : "Structural AST"}
                            </span>
                          )}
                        </div>

                        <span className="font-sans text-xs text-[#8B9099] truncate mt-0.5">
                          {item.description}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 self-end sm:self-auto font-mono text-xs text-[#71717A] flex-shrink-0">
                      {item.timestamp && (
                        <span className="text-[11px] text-[#A1A1AA]">
                          {new Date(item.timestamp).toLocaleString()}
                        </span>
                      )}

                      {item.url && (
                        <Link
                          href={item.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="key-cap key-cap--sm font-mono text-xs text-white flex items-center gap-1.5"
                        >
                          <span>View</span>
                          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                          </svg>
                        </Link>
                      )}
                    </div>
                  </div>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}

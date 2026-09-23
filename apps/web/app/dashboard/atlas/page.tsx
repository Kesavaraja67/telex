"use client";

import React, { Suspense, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { getRepos, type Repo } from "@/lib/api";
import SpotlightCard from "@/components/ui/SpotlightCard";
import { useSidebar } from "@/components/dashboard/SidebarContext";

const AtlasView = dynamic(() => import("@/components/atlas/AtlasView"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex flex-col items-center justify-center gap-3 bg-black">
      <div className="w-6 h-6 border-2 border-white/20 border-t-white rounded-full animate-spin" />
      <p className="font-mono text-xs text-[#71717A]">Loading 3D Atlas Engine…</p>
    </div>
  ),
});

function AtlasContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const paramRepoId = searchParams.get("repo");
  const { isSidebarCollapsed } = useSidebar();

  const [repos, setRepos] = useState<Repo[]>([]);
  const [selectedRepoId, setSelectedRepoId] = useState<string>(paramRepoId || "");
  const [isLoading, setIsLoading] = useState(true);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function loadRepos() {
      try {
        const data = await getRepos();
        if (!isMounted) return;
        setRepos(data);

        // Auto-select repo: param match > first repo
        if (paramRepoId && data.some((r) => r.id === paramRepoId)) {
          setSelectedRepoId(paramRepoId);
        } else if (data.length > 0) {
          setSelectedRepoId(data[0].id);
        }
      } catch (err) {
        console.error("Failed to load repos for Atlas:", err);
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    loadRepos();

    return () => {
      isMounted = false;
    };
  }, [paramRepoId]);

  const selectedRepo = repos.find((r) => r.id === selectedRepoId) || repos[0];

  const handleSelectRepo = (repoId: string) => {
    setSelectedRepoId(repoId);
    setIsDropdownOpen(false);
    router.replace(`/dashboard/atlas?repo=${repoId}`);
  };

  if (isLoading) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center gap-3 bg-black">
        <div className="w-6 h-6 border-2 border-white/20 border-t-white rounded-full animate-spin" />
        <p className="font-mono text-xs text-[#71717A]">Loading connected repositories…</p>
      </div>
    );
  }

  if (repos.length === 0) {
    return (
      <div className="w-full h-full flex items-center justify-center p-6 bg-black">
        <SpotlightCard
          spotlightColor="rgba(255, 255, 255, 0.08)"
          className="p-8 sm:p-12 bg-black/80 backdrop-blur-xl border border-white/15 rounded-2xl flex flex-col items-center text-center gap-5 shadow-2xl max-w-lg"
          enableTilt={false}
        >
          <div className="w-14 h-14 rounded-xl bg-white/5 border border-white/15 flex items-center justify-center">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-white">
              <circle cx="12" cy="5" r="2" />
              <circle cx="5" cy="19" r="2" />
              <circle cx="19" cy="19" r="2" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 7v5m0 0l-5.5 5m5.5-5l5.5 5" />
            </svg>
          </div>

          <div className="flex flex-col gap-1.5">
            <h2 className="font-mono font-bold text-lg text-white">
              No Repositories Connected
            </h2>
            <p className="font-sans text-xs text-[#A1A1AA] leading-relaxed">
              Connect a GitHub repository to explore its codebase AST, static import relationships, and live breakages in real-time 3D.
            </p>
          </div>

          <a
            href={`https://github.com/apps/${process.env.NEXT_PUBLIC_GITHUB_APP_NAME || "telex-agent-dev"}/installations/new`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-white text-black font-mono font-bold text-xs hover:bg-white/90 transition-all shadow-lg"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            <span>Connect Repository via GitHub</span>
          </a>
        </SpotlightCard>
      </div>
    );
  }

  return (
    <div className="w-full h-full flex flex-col bg-black overflow-hidden relative">
      {/* Top Header Bar: Repository Switcher & Meta */}
      <header
        className={`h-14 border-b border-white/[0.08] bg-black/85 backdrop-blur-xl ${
          isSidebarCollapsed ? "pl-36 pr-5" : "px-5"
        } flex items-center justify-between z-40 flex-shrink-0 transition-all duration-300`}
      >
        <div className="flex items-center gap-3">
          {/* Target Repo Dropdown */}
          <div className="relative">
            <button
              onClick={() => setIsDropdownOpen((prev) => !prev)}
              className="flex items-center gap-2.5 px-3 py-1.5 rounded-lg bg-white/[0.05] border border-white/15 hover:border-white/30 text-white font-mono text-xs transition-all cursor-pointer group"
            >
              <span className="w-2 h-2 rounded-full bg-white shadow-[0_0_6px_rgba(255,255,255,0.6)]" />
              <span className="text-[#71717A] text-[11px]">REPO:</span>
              <span className="font-semibold text-white tracking-wide">
                {selectedRepo?.full_name || "Select repo"}
              </span>
              <span className="text-[#71717A] text-[10px] bg-white/[0.06] px-1.5 py-0.5 rounded border border-white/5">
                {selectedRepo?.default_branch || "main"}
              </span>
              <svg
                className={`w-3.5 h-3.5 text-[#A1A1AA] transition-transform duration-200 ${
                  isDropdownOpen ? "rotate-180" : ""
                }`}
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {/* Dropdown Menu */}
            {isDropdownOpen && (
              <>
                <div
                  className="fixed inset-0 z-40"
                  onClick={() => setIsDropdownOpen(false)}
                />
                <div className="absolute left-0 top-full mt-1.5 w-72 rounded-xl bg-black/95 border border-white/15 shadow-2xl p-1.5 z-50 backdrop-blur-2xl flex flex-col gap-1 font-mono text-xs">
                  <div className="px-2.5 py-1 text-[10px] text-[#71717A] tracking-wider uppercase border-b border-white/5">
                    Select Repository ({repos.length})
                  </div>
                  <div className="max-h-60 overflow-y-auto flex flex-col gap-0.5">
                    {repos.map((repo) => {
                      const isCurrent = repo.id === selectedRepo?.id;
                      return (
                        <button
                          key={repo.id}
                          onClick={() => handleSelectRepo(repo.id)}
                          className={`flex items-center justify-between px-2.5 py-2 rounded-lg text-left transition-all cursor-pointer ${
                            isCurrent
                              ? "bg-white/10 text-white font-semibold"
                              : "text-[#A1A1AA] hover:text-white hover:bg-white/5"
                          }`}
                        >
                          <div className="flex flex-col min-w-0">
                            <span className="truncate">{repo.full_name}</span>
                            <span className="text-[10px] text-[#71717A]">
                              branch: {repo.default_branch}
                            </span>
                          </div>
                          {isCurrent && (
                            <span className="text-white text-xs">✓</span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Direct Link to Repo Details */}
          {selectedRepo && (
            <Link
              href={`/dashboard/repos/${selectedRepo.id}`}
              className="hidden sm:flex items-center gap-1.5 font-mono text-[11px] text-[#71717A] hover:text-[#E4E4E7] transition-colors"
            >
              <span>View Patches & Policies</span>
              <span>→</span>
            </Link>
          )}
        </div>

        {/* Right Info Pill */}
        <div className="flex items-center gap-2 font-mono text-xs">
          <div className="hidden md:flex items-center gap-2 px-2.5 py-1 rounded-md bg-white/[0.03] border border-white/10 text-[#71717A] text-[11px]">
            <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
            <span>3D Architecture Visualizer</span>
          </div>

          <Link
            href="/dashboard/repos"
            className="font-mono text-xs px-3 py-1.5 rounded-lg border border-white/10 hover:border-white/20 bg-white/[0.04] text-[#A1A1AA] hover:text-white transition-all"
          >
            All Repos
          </Link>
        </div>
      </header>

      {/* 3D Visualizer Canvas */}
      <div className="flex-1 w-full h-full relative overflow-hidden">
        {selectedRepo && (
          <AtlasView
            key={selectedRepo.id}
            repoId={selectedRepo.id}
            showBackButton={false}
          />
        )}
      </div>
    </div>
  );
}

export default function AtlasPage() {
  return (
    <Suspense
      fallback={
        <div className="w-full h-full flex flex-col items-center justify-center gap-3 bg-black">
          <div className="w-6 h-6 border-2 border-white/20 border-t-white rounded-full animate-spin" />
          <p className="font-mono text-xs text-[#71717A]">Loading connected repositories…</p>
        </div>
      }
    >
      <AtlasContent />
    </Suspense>
  );
}

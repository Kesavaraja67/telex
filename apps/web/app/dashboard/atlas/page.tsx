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
        className={`h-14 sidebar-panel border-b border-black/80 shadow-[0_2px_10px_rgba(0,0,0,0.8)] ${
          isSidebarCollapsed ? "pl-36 pr-5" : "px-5"
        } flex items-center justify-between z-40 flex-shrink-0 transition-all duration-300`}
      >
        <div className="flex items-center gap-3">
          {/* Target Repo Dropdown */}
          <div className="relative">
            <button
              onClick={() => setIsDropdownOpen((prev) => !prev)}
              className="key-cap key-cap--sm flex items-center gap-2.5 cursor-pointer text-white"
            >
              <span className="led" data-state="ok" style={{ width: "6px", height: "6px" }} />
              <span className="label-engraved text-[10px]">REPO:</span>
              <span className="font-semibold text-white tracking-wide">
                {selectedRepo?.full_name || "Select repo"}
              </span>
              <span className="badge-chip text-[9px] py-0 px-1.5">
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
                <div className="absolute left-0 top-full mt-1.5 w-72 metal-bezel p-[2px] z-50 shadow-2xl">
                  <div className="panel-inset rounded-[6px] p-2 flex flex-col gap-1 font-mono text-xs">
                    <div className="px-2.5 py-1 label-engraved text-[9px] border-b border-black/80 shadow-[0_1px_0_rgba(255,255,255,0.05)]">
                      Select Repository ({repos.length})
                    </div>
                    <div className="max-h-60 overflow-y-auto flex flex-col gap-1 pt-1">
                      {repos.map((repo) => {
                        const isCurrent = repo.id === selectedRepo?.id;
                        return (
                          <button
                            key={repo.id}
                            onClick={() => handleSelectRepo(repo.id)}
                            className={`flex items-center justify-between px-2.5 py-2 rounded text-left transition-all cursor-pointer ${
                              isCurrent
                                ? "nav-item-active text-white font-semibold"
                                : "nav-item-inactive text-[#A1A1AA] hover:text-white"
                            }`}
                          >
                            <div className="flex flex-col min-w-0">
                              <span className="truncate">{repo.full_name}</span>
                              <span className="text-[10px] text-[#71717A]">
                                branch: {repo.default_branch}
                              </span>
                            </div>
                            {isCurrent && (
                              <span className="led" data-state="ok" style={{ width: "6px", height: "6px" }} />
                            )}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Direct Link to Repo Details */}
          {selectedRepo && (
            <Link
              href={`/dashboard/repos/${selectedRepo.id}`}
              onClick={() => {
                if (typeof window !== "undefined") {
                  try {
                    sessionStorage.setItem(`telex_repo_${selectedRepo.id}`, JSON.stringify(selectedRepo));
                  } catch {}
                }
              }}
              className="hidden sm:flex items-center gap-1.5 label-engraved text-[11px] hover:text-white transition-colors"
            >
              <span>View Patches & Policies</span>
              <span>→</span>
            </Link>
          )}
        </div>

        {/* Right Info Pill */}
        <div className="flex items-center gap-2 font-mono text-xs">
          <div className="badge-chip hidden md:flex items-center gap-2">
            <span className="led" data-state="ok" style={{ width: "6px", height: "6px" }} />
            <span>3D Visualizer</span>
          </div>

          <Link
            href="/dashboard/repos"
            className="key-cap key-cap--sm text-white"
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

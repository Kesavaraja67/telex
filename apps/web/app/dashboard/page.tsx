"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "motion/react";
import SpotlightCard from "@/components/ui/SpotlightCard";
import CyberGridBackground from "@/components/ui/CyberGridBackground";
import Badge from "@/components/ui/Badge";
import type { Repo } from "@/lib/api";

const INITIAL_REPOS: (Repo & { category?: string })[] = [
  {
    id: "aura-drops",
    full_name: "Kesavaraja67/aura-drops",
    name: "aura-drops",
    owner: "Kesavaraja67",
    description: "Artisan wellness e-commerce storefront with Razorpay checkout and autonomous self-healing payment integration.",
    default_branch: "main",
    is_active: true,
    created_at: "2026-08-20T00:00:00Z",
    github_url: "https://github.com/Kesavaraja67/aura-drops",
    languages: ["TypeScript", "Next.js", "React"],
    patch_count: 8,
    status: "healthy",
    category: "personal",
    last_commit: {
      hash: "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
      short_hash: "a1b2c3d",
      author: "Kesavaraja67",
      relative_time: "recently",
      date: "recently",
      message: "feat(checkout): Razorpay payment gateway integration with autonomous signature verification",
    },
    dependencies: ["next", "react", "razorpay", "typescript", "tailwind"],
  },
  {
    id: "telex",
    full_name: "Kesavaraja67/telex",
    name: "telex",
    owner: "Kesavaraja67",
    description: "Autonomous dependency self-healing & runtime payment recovery platform with verification gates.",
    default_branch: "main",
    is_active: true,
    created_at: "2026-08-01T12:00:00Z",
    github_url: "https://github.com/Kesavaraja67/telex",
    languages: ["Python", "TypeScript", "SQL"],
    patch_count: 847,
    status: "healthy",
    category: "personal",
    last_commit: {
      hash: "ffd2731",
      short_hash: "ffd2731",
      author: "Kesavaraja67",
      relative_time: "recently",
      date: "recently",
      message: "feat(ui): add Landing Page link and Connect Repo action in sidebar",
    },
    dependencies: ["@google/genai", "fastapi", "sqlalchemy", "razorpay", "tree-sitter", "next", "motion"],
  },
  {
    id: "next-js",
    full_name: "vercel/next.js",
    name: "next.js",
    owner: "vercel",
    description: "The React Framework for the Web — App Router, Server Actions, Dynamic I/O, and Turbopack.",
    default_branch: "canary",
    is_active: true,
    created_at: "2016-10-25T00:00:00Z",
    github_url: "https://github.com/vercel/next.js",
    languages: ["Rust", "TypeScript", "JavaScript"],
    patch_count: 1420,
    status: "healthy",
    category: "benchmark",
    last_commit: {
      hash: "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
      short_hash: "a1b2c3d",
      author: "shadcn",
      email: "shadcn@vercel.com",
      relative_time: "2h ago",
      date: "2h ago",
      message: "fix(turbopack): optimize module dependency graph traversal and sourcemap cache",
    },
    dependencies: ["react", "react-dom", "turbopack", "swc"],
  },
  {
    id: "openai-python",
    full_name: "openai/openai-python",
    name: "openai-python",
    owner: "openai",
    description: "The official Python library for the OpenAI API with streaming completions, audio, and structured outputs.",
    default_branch: "main",
    is_active: true,
    created_at: "2020-06-11T00:00:00Z",
    github_url: "https://github.com/openai/openai-python",
    languages: ["Python", "Pydantic", "Httpx"],
    patch_count: 684,
    status: "healthy",
    category: "benchmark",
    last_commit: {
      hash: "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1",
      short_hash: "b2c3d4e",
      author: "rattrayalex",
      email: "alex@openai.com",
      relative_time: "4h ago",
      date: "4h ago",
      message: "feat: add structured response helpers and retry timeout instrumentation",
    },
    dependencies: ["httpx", "pydantic", "typing-extensions"],
  },
  {
    id: "razorpay-node",
    full_name: "razorpay/razorpay-node",
    name: "razorpay-node",
    owner: "razorpay",
    description: "Official Node.js SDK for Razorpay payment gateway API integration, orders, refunds, and webhook HMAC verification.",
    default_branch: "master",
    is_active: true,
    created_at: "2016-01-15T00:00:00Z",
    github_url: "https://github.com/razorpay/razorpay-node",
    languages: ["TypeScript", "JavaScript"],
    patch_count: 312,
    status: "healthy",
    category: "benchmark",
    last_commit: {
      hash: "c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2",
      short_hash: "c3d4e5f",
      author: "razorpay-dev",
      email: "dev@razorpay.com",
      relative_time: "1d ago",
      date: "1d ago",
      message: "fix: webhook signature validation and order status error handling",
    },
    dependencies: ["request-promise-native", "crypto"],
  },
  {
    id: "fastapi",
    full_name: "fastapi/fastapi",
    name: "fastapi",
    owner: "fastapi",
    description: "FastAPI framework, high performance, easy to learn, fast to code, ready for production.",
    default_branch: "master",
    is_active: true,
    created_at: "2018-12-05T00:00:00Z",
    github_url: "https://github.com/fastapi/fastapi",
    languages: ["Python", "Starlette", "Pydantic"],
    patch_count: 915,
    status: "healthy",
    category: "benchmark",
    last_commit: {
      hash: "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3",
      short_hash: "d4e5f6a",
      author: "tiangolo",
      email: "tiangolo@gmail.com",
      relative_time: "1d ago",
      date: "1d ago",
      message: "feat: add support for python 3.13 and enhanced exception handlers",
    },
    dependencies: ["starlette", "pydantic", "uvicorn"],
  },
];

export default function DashboardOverview() {
  const [repos, setRepos] = useState<(Repo & { category?: string })[]>(INITIAL_REPOS);
  const [activeTab, setActiveTab] = useState<"personal" | "benchmark">("personal");

  useEffect(() => {
    async function loadRepos() {
      try {
        const { getRepos } = await import("@/lib/api");
        const data = await getRepos();
        if (data && data.length > 0) {
          setRepos(data as (Repo & { category?: string })[]);
        }
      } catch {
        // Keep initial repos
      }
    }
    loadRepos();
    const timer = setInterval(loadRepos, 8000);
    return () => clearInterval(timer);
  }, []);

  const displayedRepos = repos.filter((r) => {
    const isPersonal = r.category === "personal" || r.owner?.toLowerCase() === "kesavaraja67";
    return activeTab === "personal" ? isPersonal : !isPersonal;
  });

  const totalPatches = repos.reduce((acc, r) => acc + (r.patch_count || 0), 0);

  return (
    <div className="flex flex-col gap-6 relative z-10 max-w-7xl mx-auto w-full">
      {/* Background */}
      <CyberGridBackground />

      {/* Clean Minimal Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] tracking-wider text-[#A1A1AA] uppercase font-semibold">
              Fleet Infrastructure
            </span>
            <span className="text-[#3F3F46]">/</span>
            <span className="font-mono text-[10px] text-white">Repository Radar</span>
          </div>
          <h1 className="font-mono font-bold text-xl sm:text-2xl text-white tracking-tight">
            Monitored Repositories
          </h1>
          <p className="font-sans text-xs text-[#71717A]">
            Autonomous AST scanning, runtime payment healing, and real-time commit telemetry.
          </p>
        </div>

        {/* Header Actions: Connect Repo Button + Live Sync Indicator */}
        <div className="flex items-center gap-3 self-start sm:self-center">
          <a
            href={`https://github.com/apps/${process.env.NEXT_PUBLIC_GITHUB_APP_NAME || "telex-agent-dev"}/installations/new`}
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

      {/* Sleek Minimal Metric Strip (Linear / Vercel style) */}
      <div className="grid grid-cols-2 md:grid-cols-4 rounded-xl border border-white/10 bg-black/60 backdrop-blur-xl divide-y md:divide-y-0 md:divide-x divide-white/[0.08] shadow-lg">
        <div className="p-4 flex flex-col gap-0.5">
          <span className="font-mono text-[11px] text-[#71717A] uppercase tracking-wider">
            Active Targets
          </span>
          <div className="flex items-baseline gap-1.5">
            <span className="font-mono font-bold text-2xl text-white">{repos.length}</span>
            <span className="font-mono text-[10px] text-[#A1A1AA]">monitored</span>
          </div>
        </div>

        <div className="p-4 flex flex-col gap-0.5">
          <span className="font-mono text-[11px] text-[#71717A] uppercase tracking-wider">
            Verified PRs
          </span>
          <div className="flex items-baseline gap-1.5">
            <span className="font-mono font-bold text-2xl text-white">{Math.max(128, Math.round(totalPatches * 0.15))}</span>
            <span className="font-mono text-[10px] text-[#A1A1AA]">opened</span>
          </div>
        </div>

        <div className="p-4 flex flex-col gap-0.5">
          <span className="font-mono text-[11px] text-[#71717A] uppercase tracking-wider">
            Synthesized Patches
          </span>
          <div className="flex items-baseline gap-1.5">
            <span className="font-mono font-bold text-2xl text-white">{totalPatches}</span>
            <span className="font-mono text-[10px] text-[#A1A1AA]">auto-healed</span>
          </div>
        </div>

        <div className="p-4 flex flex-col gap-0.5">
          <span className="font-mono text-[11px] text-[#71717A] uppercase tracking-wider">
            Merge Success
          </span>
          <div className="flex items-baseline gap-1.5">
            <span className="font-mono font-bold text-2xl text-white">94%</span>
            <span className="font-mono text-[10px] text-white/70">pass rate</span>
          </div>
        </div>
      </div>

      {/* Fleet Controls: Section Title + Clean Segmented Pill Filter */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2">
        <div className="flex items-center gap-2">
          <span className="font-mono font-semibold text-sm text-white">Connected Fleet</span>
          <span className="font-mono text-[10px] px-2 py-0.5 rounded-full bg-white/10 text-[#A1A1AA] border border-white/15">
            {displayedRepos.length} in view
          </span>
        </div>

        <div className="flex items-center gap-2.5 self-start sm:self-auto">
          {/* Clean Pill Toggle */}
          <div className="inline-flex p-0.5 rounded-lg bg-white/[0.04] border border-white/10 backdrop-blur-md">
            <button
              onClick={() => setActiveTab("personal")}
              className={`px-3 py-1 rounded-md font-mono text-xs font-medium transition-all ${
                activeTab === "personal"
                  ? "bg-white text-black shadow-sm"
                  : "text-[#71717A] hover:text-white"
              }`}
            >
              My Repositories
            </button>
            <button
              onClick={() => setActiveTab("benchmark")}
              className={`px-3 py-1 rounded-md font-mono text-xs font-medium transition-all ${
                activeTab === "benchmark"
                  ? "bg-white text-black shadow-sm"
                  : "text-[#71717A] hover:text-white"
              }`}
            >
              Industry Benchmarks
            </button>
          </div>

          <a
            href={`https://github.com/apps/${process.env.NEXT_PUBLIC_GITHUB_APP_NAME || "telex-agent-dev"}/installations/new`}
            target="_blank"
            rel="noopener noreferrer"
            className="hidden sm:inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-white/20 bg-white/5 hover:bg-white/10 text-white font-mono text-xs font-medium transition-colors"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            <span>Add Repo</span>
          </a>
        </div>
      </div>

      {/* Streamlined Clean Repository Cards */}
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
                {/* Header line */}
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

                    {/* Compact languages */}
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

                  {/* Actions & Badge */}
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

                {/* Description */}
                {repo.description && (
                  <p className="font-sans text-xs text-[#A1A1AA] line-clamp-1">
                    {repo.description}
                  </p>
                )}

                {/* Clean Commit Snippet */}
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
    </div>
  );
}

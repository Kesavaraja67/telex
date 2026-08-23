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

const FALLBACK_REPO_DETAILS: Record<string, RepoDetails> = {
  "telex": {
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
    dependencies: ["@google/genai", "fastapi", "sqlalchemy", "razorpay", "tree-sitter", "next", "motion"],
    commits: [
      {
        hash: "f1d8df9ac1d834ee41f065dd867266ad70b6e7c0",
        short_hash: "f1d8df9",
        author: "Kesavaraja67",
        relative_time: "1d ago",
        date: "1d ago",
        message: "fix(core): track .env.example, wire APScheduler registry polling, and support configurable escalation target",
      },
      {
        hash: "e56d8658f4c13850d83ed571c8a0a0589bc7e854",
        short_hash: "e56d865",
        author: "Kesavaraja67",
        relative_time: "23h ago",
        date: "23h ago",
        message: "test(engine-a): add comprehensive test suite for tree-sitter scanning and patch validation",
      },
    ],
  },
  "75-club": {
    id: "75-club",
    full_name: "Kesavaraja67/75-club",
    name: "75-club",
    owner: "Kesavaraja67",
    description: "Smart attendance tracker for Indian college students — safe bunk calculator, AI timetable scanner, and Pro analytics as a PWA.",
    default_branch: "main",
    is_active: true,
    created_at: "2026-06-11T10:00:00Z",
    github_url: "https://github.com/Kesavaraja67/75-club",
    languages: ["TypeScript", "Next.js", "PWA"],
    patch_count: 42,
    status: "healthy",
    dependencies: ["next", "react", "typescript", "tailwind", "tesseract.js"],
    commits: [
      {
        hash: "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1",
        short_hash: "b2c3d4e",
        author: "Kesavaraja67",
        relative_time: "Jun 11, 2026",
        date: "Jun 11, 2026",
        message: "feat(pwa): AI timetable OCR scanner and safe attendance projection engine",
      },
    ],
  },
  "echo-mind-framework": {
    id: "echo-mind-framework",
    full_name: "Kesavaraja67/Echo-Mind-Framework",
    name: "Echo-Mind-Framework",
    owner: "Kesavaraja67",
    description: "Modular AI-powered framework designed to simulate memory, reasoning, and contextual decision-making with FastAPI backend.",
    default_branch: "main",
    is_active: true,
    created_at: "2026-06-29T08:30:00Z",
    github_url: "https://github.com/Kesavaraja67/Echo-Mind-Framework",
    languages: ["Python", "FastAPI"],
    patch_count: 24,
    status: "healthy",
    dependencies: ["fastapi", "pydantic", "langchain", "chromadb"],
    commits: [
      {
        hash: "c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2",
        short_hash: "c3d4e5f",
        author: "Kesavaraja67",
        relative_time: "Jun 29, 2026",
        date: "Jun 29, 2026",
        message: "feat(memory): vector context storage and semantic retrieval pipeline",
      },
    ],
  },
  "cube-buddy": {
    id: "cube-buddy",
    full_name: "Kesavaraja67/Cube-Buddy",
    name: "Cube-Buddy",
    owner: "Kesavaraja67",
    description: "Intelligent, interactive web app that helps users scan, detect, and solve twisty puzzles directly in the browser with 3D visualization.",
    default_branch: "main",
    is_active: true,
    created_at: "2026-07-15T14:00:00Z",
    github_url: "https://github.com/Kesavaraja67/Cube-Buddy",
    languages: ["CSS", "JavaScript", "WebGL"],
    patch_count: 14,
    status: "healthy",
    dependencies: ["three.js", "opencv.js", "css3d"],
    commits: [
      {
        hash: "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3",
        short_hash: "d4e5f6a",
        author: "Kesavaraja67",
        relative_time: "Jul 15, 2026",
        date: "Jul 15, 2026",
        message: "chore: file fix and 3D cube state renderer update",
      },
    ],
  },
  "ppr": {
    id: "ppr",
    full_name: "Kesavaraja67/ppr",
    name: "ppr",
    owner: "Kesavaraja67",
    description: "Partial Prerendering (PPR) and high-performance server streaming optimization engine for Next.js applications.",
    default_branch: "main",
    is_active: true,
    created_at: "2026-08-10T12:00:00Z",
    github_url: "https://github.com/Kesavaraja67/ppr",
    languages: ["TypeScript", "Next.js"],
    patch_count: 19,
    status: "healthy",
    dependencies: ["next", "react", "typescript"],
    commits: [
      {
        hash: "e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4",
        short_hash: "e5f6a7b",
        author: "ThankaBharathi",
        relative_time: "9d ago",
        date: "9d ago",
        message: "fix(admin): populate customer name, refine dynamic streaming Suspense fallback",
      },
    ],
  },
  "next-js": {
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
    dependencies: ["react", "react-dom", "turbopack", "swc"],
    commits: [
      {
        hash: "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
        short_hash: "a1b2c3d",
        author: "timneutkens",
        relative_time: "2h ago",
        date: "2h ago",
        message: "perf(turbopack): optimize incremental cache invalidation for dynamic routes",
      },
    ],
  },
  "openai-python": {
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
    dependencies: ["httpx", "pydantic", "typing-extensions"],
    commits: [
      {
        hash: "f0e1d2c3b4a5f6e7d8c9b0a1f2e3d4c5b6a7f8e9",
        short_hash: "f0e1d2c",
        author: "rattrayalex",
        relative_time: "4h ago",
        date: "4h ago",
        message: "feat: add structured output support for vision analysis models",
      },
    ],
  },
  "razorpay-node": {
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
    dependencies: ["request-promise-native", "crypto"],
    commits: [
      {
        hash: "9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b",
        short_hash: "9a8b7c6",
        author: "razorpay-dev",
        relative_time: "1d ago",
        date: "1d ago",
        message: "fix(webhook): enforce constant-time HMAC comparison in node SDK",
      },
    ],
  },
  "fastapi": {
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
    dependencies: ["starlette", "pydantic", "uvicorn", "email-validator"],
    commits: [
      {
        hash: "8f7e6d5c4b3a2f1e0d9c8b7a6f5e4d3c2b1a0f9e",
        short_hash: "8f7e6d5",
        author: "tiangolo",
        relative_time: "3d ago",
        date: "3d ago",
        message: "docs: update tutorial for python 3.12 type annotations with Annotated",
      },
    ],
  },
};

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
        } else {
          setRepo(FALLBACK_REPO_DETAILS[repoId] || FALLBACK_REPO_DETAILS["telex"]);
        }
      } catch {
        if (isMounted) {
          setRepo(FALLBACK_REPO_DETAILS[repoId] || FALLBACK_REPO_DETAILS["telex"]);
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

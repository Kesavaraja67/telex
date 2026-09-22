"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { API_BASE } from "@/lib/api";
import { AtlasScene } from "./AtlasScene";
import { CodePreviewPanel } from "./CodePreviewPanel";
import type { ActiveIncident, AtlasGraphPayload, AtlasSelection } from "./types";

type LoadState =
  | { kind: "computing"; commitSha: string }
  | { kind: "ready"; data: AtlasGraphPayload }
  | { kind: "failed"; error: string }
  | { kind: "idle" };

function getAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("telex_token");
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

export default function AtlasView({
  repoId,
  showBackButton = true,
}: {
  repoId: string;
  showBackButton?: boolean;
}) {
  const router = useRouter();
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<AtlasScene | null>(null);

  const [state, setState] = useState<LoadState>({ kind: "idle" });
  const [repoName, setRepoName] = useState<string>("");
  const [selection, setSelection] = useState<AtlasSelection | null>(null);
  const [activeIncidents, setActiveIncidents] = useState<ActiveIncident[]>([]);
  const [legendOpen, setLegendOpen] = useState(true);
  const [controlsOpen, setControlsOpen] = useState(true);
  const [computeSeconds, setComputeSeconds] = useState(0);

  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollStartedAt = useRef<number>(0);

  // 1. Polling and loading graph
  const load = useCallback(
    async (opts: { refresh?: boolean; pinnedSha?: string } = {}) => {
      const params = new URLSearchParams();
      if (opts.pinnedSha) params.set("commit_sha", opts.pinnedSha);
      if (opts.refresh) params.set("refresh", "true");

      try {
        const res = await fetch(`${API_BASE}/api/repos/${repoId}/atlas/graph?${params}`, {
          credentials: "include",
          headers: getAuthHeaders(),
        });
        const body = await res.json();

        if (body.repo_full_name) {
          setRepoName(body.repo_full_name);
        }

        if (res.status === 200 && body.status === "ready") {
          setState({ kind: "ready", data: body });
          return;
        }
        if (body.status === "failed") {
          setState({ kind: "failed", error: body.error || "Graph build failed." });
          return;
        }

        // Computing (202)
        setState({ kind: "computing", commitSha: body.commit_sha });
        if (pollStartedAt.current === 0) pollStartedAt.current = Date.now();
        if (Date.now() - pollStartedAt.current > 180_000) {
          setState({ kind: "failed", error: "Timed out waiting for the graph to build." });
          return;
        }
        pollTimer.current = setTimeout(() => load({ pinnedSha: body.commit_sha }), 1500);
      } catch (err: any) {
        setState({ kind: "failed", error: err.message || "Network error while fetching graph." });
      }
    },
    [repoId]
  );

  // 2. Compute duration counter
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;
    if (state.kind === "computing") {
      interval = setInterval(() => {
        setComputeSeconds((s) => s + 1);
      }, 1000);
    } else {
      setComputeSeconds(0);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [state.kind]);

  // 3. Breakage overlay: active incidents + SSE stream
  useEffect(() => {
    let isMounted = true;

    async function fetchActiveIncidentsAndSeedBreakage() {
      try {
        const res = await fetch(`${API_BASE}/api/repos/${repoId}/incidents/active`, {
          credentials: "include",
          headers: getAuthHeaders(),
        });
        if (!res.ok) return;
        const incidents: ActiveIncident[] = await res.json();
        if (!isMounted) return;
        setActiveIncidents(incidents);

        // Fetch graph details for each active incident to get implicated files
        const brokenSet = new Set<string>();
        await Promise.allSettled(
          incidents.map(async (inc) => {
            try {
              const gRes = await fetch(
                `${API_BASE}/api/repos/${repoId}/incidents/${inc.detected_change_id}/graph`,
                { credentials: "include", headers: getAuthHeaders() }
              );
              if (gRes.ok) {
                const gData = await gRes.json();
                gData.nodes?.forEach((n: any) => {
                  if (n.status !== "patched") {
                    brokenSet.add(n.file_path);
                  }
                });
              }
            } catch {
              // Ignore single incident fetch failure
            }
          })
        );

        if (isMounted && sceneRef.current) {
          sceneRef.current.setBreakage(brokenSet);
        }
      } catch {
        // Active incidents optional
      }
    }

    fetchActiveIncidentsAndSeedBreakage();

    // Subscribe to SSE stream for live updates
    let es: EventSource | null = null;
    try {
      es = new EventSource(`${API_BASE}/api/repos/${repoId}/incidents/stream`, {
        withCredentials: true,
      });

      es.onmessage = () => {
        // On any incident event, refresh active breakage
        fetchActiveIncidentsAndSeedBreakage();
      };
    } catch {
      // EventSource fallback
    }

    return () => {
      isMounted = false;
      if (es) es.close();
    };
  }, [repoId]);

  // 4. Keyboard shortcuts (F: center, R: refresh, L: legend, Esc: close)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      if (e.key === "Escape") {
        if (selection) {
          setSelection(null);
        } else {
          router.back();
        }
      } else if (e.key === "f" || e.key === "F") {
        sceneRef.current?.resetView();
      } else if (e.key === "r" || e.key === "R") {
        pollStartedAt.current = 0;
        load({ refresh: true });
      } else if (e.key === "l" || e.key === "L") {
        setLegendOpen((prev) => !prev);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selection, router, load]);

  // 5. Mount lifecycle
  useEffect(() => {
    document.body.style.overflow = "hidden";
    pollStartedAt.current = 0;
    load();

    return () => {
      document.body.style.overflow = "";
      if (pollTimer.current) clearTimeout(pollTimer.current);
      sceneRef.current?.destroy();
      sceneRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repoId]);

  // 6. Scene initialization once data is ready
  useEffect(() => {
    if (state.kind !== "ready" || !containerRef.current) return;

    const scene = new AtlasScene(containerRef.current, {
      onSelect: (sel) => {
        setSelection(sel);
        if (sel.nodeId) {
          scene.focusNode(sel.nodeId);
        }
      },
      repoId,
      commitSha: state.data.commit_sha,
    });
    scene.init(state.data);
    sceneRef.current = scene;

    return () => {
      scene.destroy();
      sceneRef.current = null;
    };
  }, [state, repoId]);

  return (
    <div className="w-full h-full relative select-none bg-black overflow-hidden font-sans">
      <div ref={containerRef} className="absolute inset-0" />

      {/* Top HUD Bar */}
      <div className="absolute top-0 left-0 right-0 flex items-center justify-between px-5 py-4 pointer-events-none z-40">
        <div className="pointer-events-auto flex items-center gap-2.5">
          {showBackButton && (
            <button
              onClick={() => router.push("/dashboard/repos")}
              className="font-mono text-xs px-3.5 py-1.5 rounded-lg border border-white/15 bg-black/70 backdrop-blur text-[#A1A1AA] hover:text-white hover:border-white/30 transition-all cursor-pointer flex items-center gap-1.5 shadow-sm"
            >
              <span>←</span>
              <span>Repositories</span>
            </button>
          )}

          {repoName && (
            <div className="flex items-center gap-2 font-mono text-xs text-[#E4E4E7] bg-black/70 backdrop-blur px-3 py-1.5 rounded-lg border border-white/10 shadow-sm">
              <svg className="w-3.5 h-3.5 text-[#5EEAD4]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4" />
                <path d="M9 18c-4.51 2-5-2-7-2" />
              </svg>
              <span className="font-medium text-white">{repoName}</span>
              {state.kind === "ready" && state.data.commit_sha && (
                <span className="text-[#71717A] text-[10px] bg-white/[0.06] px-1.5 py-0.5 rounded border border-white/5">
                  {state.data.commit_sha.slice(0, 7)}
                </span>
              )}
            </div>
          )}
        </div>

        <div className="pointer-events-auto flex items-center gap-2">
          {/* Reset Camera Button */}
          {state.kind === "ready" && (
            <button
              onClick={() => sceneRef.current?.resetView()}
              title="Reset camera perspective (F)"
              className="font-mono text-xs px-2.5 py-1.5 rounded-lg border border-white/15 bg-black/70 backdrop-blur text-[#A1A1AA] hover:text-white hover:border-white/30 transition-all cursor-pointer flex items-center gap-1.5 shadow-sm"
            >
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
                <circle cx="12" cy="12" r="3" />
                <path d="M3 12h3m12 0h3M12 3v3m0 12v3" />
              </svg>
              <span>Reset Camera</span>
            </button>
          )}

          {state.kind === "ready" && (
            <div className="flex items-center gap-3 font-mono text-xs text-[#71717A] bg-black/70 backdrop-blur px-3.5 py-1.5 rounded-lg border border-white/10">
              <span className="text-white font-medium">{state.data.node_count} files</span>
              <span className="text-[#3F3F46]">·</span>
              <span>{state.data.edge_count} imports</span>
              {state.data.truncated && (
                <span className="text-[#E5A93C]">· first {state.data.node_count}</span>
              )}
            </div>
          )}

          {state.kind === "computing" && (
            <div className="flex items-center gap-2 font-mono text-xs text-[#A1A1AA] bg-black/70 backdrop-blur px-3 py-1.5 rounded-lg border border-white/10">
              <div className="w-2.5 h-2.5 rounded-full bg-teal-400 animate-pulse" />
              <span>Analyzing AST… ({computeSeconds}s)</span>
            </div>
          )}

          {/* Always Visible Refresh / Re-scan Button */}
          <button
            onClick={() => {
              pollStartedAt.current = 0;
              load({ refresh: true });
            }}
            title="Force re-scan and rebuild import graph (R)"
            className="font-mono text-xs px-3 py-1.5 rounded-lg border border-white/15 bg-black/70 backdrop-blur text-[#E4E4E7] hover:text-white hover:border-white/35 hover:bg-white/[0.08] transition-all cursor-pointer flex items-center gap-1.5 shadow-sm"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Cinematic Computing / Loading State */}
      {state.kind === "computing" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 z-30 pointer-events-none bg-black/40 backdrop-blur-[2px]">
          <div className="relative flex items-center justify-center">
            <div className="w-16 h-16 rounded-full border border-teal-500/20 animate-ping absolute" />
            <div className="w-12 h-12 rounded-full border-2 border-teal-400/30 border-t-teal-400 animate-spin" />
            <div className="w-3 h-3 rounded-full bg-teal-400 shadow-[0_0_12px_#5eead4]" />
          </div>
          <div className="flex flex-col items-center gap-1.5 text-center">
            <p className="font-mono text-xs font-semibold tracking-wide text-white uppercase">
              {computeSeconds < 2
                ? "Acquiring repository AST snapshot…"
                : computeSeconds < 5
                ? "Extracting module dependencies & imports…"
                : "Solving 3D layered spatial coordinates…"}
            </p>
            <p className="font-mono text-[11px] text-[#71717A]">
              Analyzing live tree · Caching graph for your team ({computeSeconds}s)
            </p>
          </div>
        </div>
      )}

      {/* Empty State */}
      {state.kind === "ready" && state.data.node_count === 0 && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-center px-6 z-30 bg-black/80">
          <p className="font-mono text-sm text-white font-semibold">No files detected in default branch</p>
          <p className="font-mono text-xs text-[#71717A] max-w-sm">
            This repository appears to be empty or contains no supported files on its default branch.
          </p>
          <button
            onClick={() => {
              pollStartedAt.current = 0;
              load({ refresh: true });
            }}
            className="mt-2 px-4 py-2 rounded-lg bg-white text-black font-mono text-xs font-semibold hover:bg-white/90 transition-all cursor-pointer"
          >
            Re-scan repository
          </button>
        </div>
      )}

      {/* Failure State */}
      {state.kind === "failed" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-center px-6 z-30 bg-black/80">
          <p className="font-mono text-sm text-white font-semibold">Couldn&apos;t build the Atlas.</p>
          <p className="font-mono text-xs text-[#71717A] max-w-sm">{state.error}</p>
          <button
            onClick={() => {
              pollStartedAt.current = 0;
              load({ refresh: true });
            }}
            className="mt-2 px-4 py-2 rounded-lg bg-white text-black font-mono text-xs font-semibold hover:bg-white/90 transition-all cursor-pointer"
          >
            Try again
          </button>
        </div>
      )}

      {/* Legend — bottom left */}
      {state.kind === "ready" && (
        <div className="absolute bottom-4 left-5 z-40 font-mono text-[11px] text-[#A1A1AA]">
          {legendOpen ? (
            <div className="bg-black/70 backdrop-blur border border-white/10 rounded-lg p-3 flex flex-col gap-2 min-w-[200px]">
              <div className="flex items-center justify-between text-[#71717A] text-[10px] pb-1 border-b border-white/10">
                <span>GRAPH LEGEND (L)</span>
                <button
                  onClick={() => setLegendOpen(false)}
                  className="hover:text-white transition-colors cursor-pointer"
                >
                  ✕
                </button>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3.5 h-0.5 bg-white/30 rounded" />
                <span className="text-[#D4D4D8]">Folder hierarchy</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3.5 h-0.5 bg-[#5EEAD4] rounded" />
                <span className="text-[#D4D4D8]">Static import</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded bg-white/10 border border-white/20 flex items-center justify-center text-[8px] text-[#A1A1AA]">
                  ⚠
                </span>
                <span className="text-[#D4D4D8]">Unresolved import</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3.5 h-0.5 bg-[#E11D48] rounded" />
                <span className="text-[#FDA4AF]">Broken by active incident</span>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setLegendOpen(true)}
              className="px-2.5 py-1.5 rounded-lg border border-white/15 bg-black/60 backdrop-blur hover:text-white transition-all cursor-pointer"
            >
              ⓘ Legend (L)
            </button>
          )}
        </div>
      )}

      {/* Floating 3D Navigation Controls Guide — bottom center */}
      {state.kind === "ready" && controlsOpen && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-40 hidden sm:flex items-center gap-3 px-3.5 py-1.5 rounded-full bg-black/75 backdrop-blur border border-white/10 font-mono text-[10px] text-[#A1A1AA] shadow-lg">
          <span className="text-[#5EEAD4]">✦ 3D Atlas</span>
          <span className="text-[#3F3F46]">·</span>
          <span>Left Drag to Orbit</span>
          <span className="text-[#3F3F46]">·</span>
          <span>Scroll to Zoom</span>
          <span className="text-[#3F3F46]">·</span>
          <span>Click to Inspect</span>
          <span className="text-[#3F3F46]">·</span>
          <span className="flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 rounded bg-white/10 text-white text-[9px]">F</kbd>
            <span>Center</span>
          </span>
          <button
            onClick={() => setControlsOpen(false)}
            className="text-[#71717A] hover:text-white ml-1 transition-colors cursor-pointer"
            title="Dismiss hint"
          >
            ✕
          </button>
        </div>
      )}

      {/* Slide-in Code Preview Panel */}
      {selection && (
        <CodePreviewPanel
          repoId={repoId}
          selection={selection}
          activeIncidents={activeIncidents}
          commitSha={state.kind === "ready" ? state.data.commit_sha : "HEAD"}
          onClose={() => setSelection(null)}
        />
      )}
    </div>
  );
}

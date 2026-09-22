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

export default function AtlasView({ repoId }: { repoId: string }) {
  const router = useRouter();
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<AtlasScene | null>(null);

  const [state, setState] = useState<LoadState>({ kind: "idle" });
  const [selection, setSelection] = useState<AtlasSelection | null>(null);
  const [activeIncidents, setActiveIncidents] = useState<ActiveIncident[]>([]);
  const [legendOpen, setLegendOpen] = useState(true);

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
        });
        const body = await res.json();

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

  // 2. Breakage overlay: active incidents + SSE stream
  useEffect(() => {
    let isMounted = true;

    async function fetchActiveIncidentsAndSeedBreakage() {
      try {
        const res = await fetch(`${API_BASE}/api/repos/${repoId}/incidents/active`, {
          credentials: "include",
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
                { credentials: "include" }
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

  // 3. Mount lifecycle
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

  // 4. Scene initialization once data is ready
  useEffect(() => {
    if (state.kind !== "ready" || !containerRef.current) return;

    const scene = new AtlasScene(containerRef.current, {
      onSelect: setSelection,
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
        <button
          onClick={() => router.back()}
          className="pointer-events-auto font-mono text-xs px-3.5 py-1.5 rounded-lg border border-white/15 bg-black/70 backdrop-blur text-[#A1A1AA] hover:text-white hover:border-white/30 transition-all cursor-pointer flex items-center gap-1.5"
        >
          <span>←</span>
          <span>Close Atlas</span>
        </button>

        <div className="pointer-events-auto flex items-center gap-2">
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
              <span>Analyzing AST…</span>
            </div>
          )}

          {/* Always Visible Refresh / Re-scan Button */}
          <button
            onClick={() => {
              pollStartedAt.current = 0;
              load({ refresh: true });
            }}
            title="Force re-scan and rebuild import graph"
            className="font-mono text-xs px-3 py-1.5 rounded-lg border border-white/15 bg-black/70 backdrop-blur text-[#E4E4E7] hover:text-white hover:border-white/35 hover:bg-white/[0.08] transition-all cursor-pointer flex items-center gap-1.5 shadow-sm"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Center states */}
      {state.kind === "computing" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 z-30 pointer-events-none">
          <div className="w-10 h-10 border border-white/20 border-t-white/80 rounded-full animate-spin" />
          <p className="font-mono text-xs text-[#A1A1AA]">Mapping repository structure…</p>
        </div>
      )}

      {state.kind === "failed" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-center px-6 z-30 bg-black/80">
          <p className="font-mono text-sm text-white font-semibold">Couldn't build the Atlas.</p>
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
                <span>GRAPH LEGEND</span>
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
              ⓘ Legend
            </button>
          )}
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

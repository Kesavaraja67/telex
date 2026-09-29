"use client";

import { useEffect, useState, useMemo } from "react";
import { API_BASE } from "@/lib/api";
import type { AtlasSelection, ActiveIncident } from "./types";
import { getLanguageStyle } from "./CardTextureAtlas";

interface CodePreviewPanelProps {
  repoId: string;
  selection: AtlasSelection;
  activeIncidents?: ActiveIncident[];
  commitSha?: string;
  onClose: () => void;
  onSelectNode?: (path: string) => void;
}

interface FileContentState {
  status: "loading" | "ready" | "error" | "binary";
  content?: string;
  error?: string;
}

interface NeighborsState {
  status: "loading" | "ready" | "error";
  imports: string[];
  importedBy: string[];
}

export function CodePreviewPanel({
  repoId,
  selection,
  activeIncidents = [],
  commitSha = "HEAD",
  onClose,
  onSelectNode,
}: CodePreviewPanelProps) {
  const { nodeId, brokenBy, node } = selection;
  const isBinary = node?.is_binary ?? false;
  const ext = node?.ext ?? "";
  const langStyle = getLanguageStyle(ext, isBinary);

  const [activeTab, setActiveTab] = useState<"code" | "deps">("code");
  const [contentState, setContentState] = useState<FileContentState>(
    isBinary ? { status: "binary" } : { status: "loading" }
  );
  const [neighborsState, setNeighborsState] = useState<NeighborsState>({
    status: "loading",
    imports: [],
    importedBy: [],
  });

  // 1. Fetch file content
  useEffect(() => {
    if (isBinary) {
      setContentState({ status: "binary" });
      return;
    }

    let isMounted = true;
    setContentState({ status: "loading" });

    const params = new URLSearchParams({
      path: nodeId,
      ref: commitSha,
    });

    const headers: Record<string, string> = {};
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("telex_token");
      if (token) headers["Authorization"] = `Bearer ${token}`;
    }

    fetch(`${API_BASE}/api/repos/${repoId}/atlas/file?${params}`, {
      credentials: "include",
      headers,
    })
      .then(async (res) => {
        if (!res.ok) {
          if (res.status === 415) return { status: "binary" as const };
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `HTTP ${res.status}`);
        }
        return res.json();
      })
      .then((data) => {
        if (!isMounted) return;
        if (data.status === "binary") {
          setContentState({ status: "binary" });
        } else {
          setContentState({ status: "ready", content: data.content });
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        setContentState({ status: "error", error: err.message || "Failed to load content." });
      });

    return () => {
      isMounted = false;
    };
  }, [repoId, nodeId, commitSha, isBinary]);

  // 2. Fetch neighbors (imports & importedBy) from /neighbors endpoint
  useEffect(() => {
    let isMounted = true;
    setNeighborsState({ status: "loading", imports: [], importedBy: [] });

    const headers: Record<string, string> = {};
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("telex_token");
      if (token) headers["Authorization"] = `Bearer ${token}`;
    }

    const params = new URLSearchParams({ path: nodeId });
    fetch(`${API_BASE}/api/repos/${repoId}/atlas/neighbors?${params}`, {
      credentials: "include",
      headers,
    })
      .then(async (res) => {
        if (!res.ok) throw new Error("Failed to load neighbors");
        return res.json();
      })
      .then((data) => {
        if (!isMounted) return;
        setNeighborsState({
          status: "ready",
          imports: data.imports || [],
          importedBy: data.imported_by || [],
        });
      })
      .catch(() => {
        if (!isMounted) return;
        setNeighborsState({ status: "error", imports: [], importedBy: [] });
      });

    return () => {
      isMounted = false;
    };
  }, [repoId, nodeId]);

  // Implicated incidents
  const incidentDetails = useMemo(() => {
    if (brokenBy.length === 0) return [];
    return activeIncidents.filter((inc) => brokenBy.includes(inc.detected_change_id));
  }, [brokenBy, activeIncidents]);

  const totalDepsCount = neighborsState.imports.length + neighborsState.importedBy.length;

  return (
    <div
      role="dialog"
      aria-label={`Code preview for ${node?.name || nodeId}`}
      className="fixed inset-y-0 right-0 w-full sm:w-[580px] z-50 sidebar-panel border-l flex flex-col shadow-[-16px_0_48px_rgba(0,0,0,0.85)] animate-in slide-in-from-right duration-200 bg-[#0c0c0e]/95 backdrop-blur-xl"
    >
      {/* Top Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-white/10 bg-black/40">
        <div className="flex items-center gap-3 min-w-0">
          <span
            className="badge-chip font-mono text-xs font-bold px-2.5 py-1 text-white flex-shrink-0"
            style={{ backgroundColor: langStyle.bg, color: langStyle.text }}
          >
            {langStyle.label}
          </span>
          <div className="flex flex-col min-w-0">
            <h2 className="font-mono text-sm font-semibold text-white truncate tracking-tight">
              {node?.name || nodeId.split("/").pop()}
            </h2>
            <span className="font-mono text-[11px] text-[#7E7E8A] truncate">
              {nodeId}
            </span>
          </div>
        </div>

        <button
          onClick={onClose}
          aria-label="Close code preview panel"
          className="key-cap key-cap--sm w-8 h-8 flex items-center justify-center cursor-pointer flex-shrink-0 hover:text-white transition-colors"
        >
          ✕
        </button>
      </div>

      {/* Skeuomorphic Sub-Navigation Tabs */}
      <div className="flex items-center gap-2 px-5 py-2.5 border-b border-white/5 bg-white/[0.02]">
        <button
          type="button"
          onClick={() => setActiveTab("code")}
          className={`px-3 py-1 rounded text-xs font-mono font-medium transition-all cursor-pointer flex items-center gap-1.5 ${
            activeTab === "code"
              ? "bg-white/15 text-white shadow-inner border border-white/20"
              : "text-[#8E8E93] hover:text-white hover:bg-white/5 border border-transparent"
          }`}
        >
          <span>Source Code</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("deps")}
          className={`px-3 py-1 rounded text-xs font-mono font-medium transition-all cursor-pointer flex items-center gap-1.5 ${
            activeTab === "deps"
              ? "bg-white/15 text-white shadow-inner border border-white/20"
              : "text-[#8E8E93] hover:text-white hover:bg-white/5 border border-transparent"
          }`}
        >
          <span>Dependencies</span>
          {neighborsState.status === "ready" && (
            <span className="font-mono text-[10px] px-1.5 py-0.2 rounded-full bg-white/10 text-white/90">
              {totalDepsCount}
            </span>
          )}
        </button>
      </div>

      {/* Breakage Notice Banner (Red overlay strictly for active incidents) */}
      {brokenBy.length > 0 && (
        <div className="px-5 py-3 bg-[#E11D48]/10 border-b border-[#E11D48]/30 flex flex-col gap-1.5">
          <div className="flex items-center gap-2">
            <span className="led" data-state="fault" />
            <span className="font-mono text-xs font-semibold text-[#E11D48] tracking-tight">
              Touched by Active Incident Breakage
            </span>
          </div>
          {incidentDetails.length > 0 ? (
            incidentDetails.map((inc) => (
              <div
                key={inc.detected_change_id}
                className="font-mono text-[11px] text-[#FDA4AF] flex items-center gap-2 pl-4"
              >
                <span>↳</span>
                <span className="font-semibold text-white">{inc.package}:</span>
                <span className="line-through text-[#FDA4AF]/70">{inc.symbol_old}</span>
                <span>→</span>
                <span className="text-white font-medium">{inc.symbol_new || "removed"}</span>
              </div>
            ))
          ) : (
            <p className="font-mono text-[11px] text-[#FDA4AF] pl-4">
              Direct call site implicated in upstream breaking change.
            </p>
          )}
        </div>
      )}

      {/* Unresolved Imports Warning Section (Honesty requirement Section 1.14) */}
      {node && node.unresolved_import_count > 0 && (
        <div className="px-5 py-2.5 bg-amber-500/[0.06] border-b border-amber-500/20 flex flex-col gap-1">
          <span className="font-mono text-[10px] text-amber-300/90 flex items-center gap-1.5">
            <span>⚠</span> {node.unresolved_import_count} unresolved / dynamic static specifier(s):
          </span>
          <div className="flex flex-wrap gap-1.5 pl-4">
            {node.unresolved_specifiers.map((spec, i) => (
              <code
                key={i}
                className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 border border-amber-500/20 text-amber-200"
              >
                {spec}
              </code>
            ))}
          </div>
        </div>
      )}

      {/* Tab 1: Source Code View */}
      {activeTab === "code" && (
        <div className="flex-1 overflow-auto p-5 font-mono text-xs leading-relaxed select-text">
          {contentState.status === "loading" && (
            <div className="h-64 flex flex-col items-center justify-center gap-3">
              <div className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse shadow-[0_0_6px_rgba(255,255,255,0.6)]" />
                <span className="w-1.5 h-1.5 rounded-full bg-white/60 animate-pulse [animation-delay:200ms]" />
                <span className="w-1.5 h-1.5 rounded-full bg-white/30 animate-pulse [animation-delay:400ms]" />
              </div>
              <span className="font-mono text-xs text-[#71717A] tracking-wider uppercase">Fetching file AST…</span>
            </div>
          )}

          {contentState.status === "binary" && (
            <div className="h-64 flex flex-col items-center justify-center gap-3 text-center px-4">
              <span className="text-3xl text-[#52525B]">▧</span>
              <span className="font-mono text-sm text-white font-medium">
                Binary or media file
              </span>
              <p className="font-mono text-xs text-[#71717A] max-w-xs">
                Preview is disabled for binary assets to protect bandwidth and memory.
              </p>
            </div>
          )}

          {contentState.status === "error" && (
            <div className="h-64 flex flex-col items-center justify-center gap-3 text-center px-4">
              <span className="font-mono text-xs text-[#E5A93C]">Unable to load file content</span>
              <p className="font-mono text-[11px] text-[#71717A]">{contentState.error}</p>
            </div>
          )}

          {contentState.status === "ready" && contentState.content && (
            <div className="relative">
              <pre className="text-xs leading-5 text-[#E4E4E7] font-mono whitespace-pre overflow-x-auto tab-4">
                {contentState.content.split("\n").map((line, idx) => (
                  <div key={idx} className="table-row hover:bg-white/[0.03]">
                    <span className="table-cell pr-4 text-right select-none text-[#52525B] text-[11px] w-10">
                      {idx + 1}
                    </span>
                    <span className="table-cell">{line || " "}</span>
                  </div>
                ))}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Dependencies & Neighbors Inspector View */}
      {activeTab === "deps" && (
        <div className="flex-1 overflow-auto p-5 space-y-6 font-mono text-xs">
          {neighborsState.status === "loading" && (
            <div className="h-64 flex flex-col items-center justify-center gap-3">
              <div className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_6px_rgba(34,211,238,0.6)]" />
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400/60 animate-pulse [animation-delay:200ms]" />
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400/30 animate-pulse [animation-delay:400ms]" />
              </div>
              <span className="font-mono text-xs text-[#71717A] tracking-wider uppercase">Loading dependency graph…</span>
            </div>
          )}

          {neighborsState.status !== "loading" && (
            <>
              {/* Section 1: Imports (Outgoing Edges) */}
              <div className="space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-[#A1A1AA] uppercase tracking-wider flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-blue-500/80" />
                    Imports ({neighborsState.imports.length})
                  </span>
                  <span className="text-[10px] text-[#71717A]">Files this module depends on</span>
                </div>

                {neighborsState.imports.length === 0 ? (
                  <div className="p-3 rounded-lg border border-white/5 bg-white/[0.02] text-[#71717A] text-xs">
                    No static internal imports detected (leaf dependency or standalone module).
                  </div>
                ) : (
                  <div className="divide-y divide-white/5 border border-white/10 rounded-lg overflow-hidden bg-black/20">
                    {neighborsState.imports.map((tgt) => {
                      const tgtExt = tgt.includes(".") ? `.${tgt.split(".").pop()}` : "";
                      const tgtStyle = getLanguageStyle(tgtExt, false);
                      return (
                        <div
                          key={tgt}
                          className="flex items-center justify-between p-2.5 hover:bg-white/[0.04] transition-colors group"
                        >
                          <div className="flex items-center gap-2.5 min-w-0">
                            <span
                              className="font-mono text-[9px] font-bold px-1.5 py-0.5 rounded text-white flex-shrink-0"
                              style={{ backgroundColor: tgtStyle.bg, color: tgtStyle.text }}
                            >
                              {tgtStyle.label}
                            </span>
                            <div className="flex flex-col min-w-0">
                              <span className="text-white text-xs font-semibold truncate group-hover:text-cyan-400 transition-colors">
                                {tgt.split("/").pop()}
                              </span>
                              <span className="text-[10px] text-[#71717A] truncate">{tgt}</span>
                            </div>
                          </div>

                          {onSelectNode && (
                            <button
                              type="button"
                              onClick={() => onSelectNode(tgt)}
                              title={`Focus ${tgt} in Atlas`}
                              className="px-2 py-1 rounded bg-white/5 hover:bg-cyan-500/20 text-[#A1A1AA] hover:text-cyan-300 border border-white/10 hover:border-cyan-500/30 text-[10px] font-mono flex items-center gap-1 transition-all cursor-pointer flex-shrink-0"
                            >
                              <span>Focus</span>
                              <span>↗</span>
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Section 2: Imported By (Incoming Edges) */}
              <div className="space-y-2.5 pt-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-[#A1A1AA] uppercase tracking-wider flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-500/80" />
                    Imported By ({neighborsState.importedBy.length})
                  </span>
                  <span className="text-[10px] text-[#71717A]">Files that depend on this module</span>
                </div>

                {neighborsState.importedBy.length === 0 ? (
                  <div className="p-3 rounded-lg border border-white/5 bg-white/[0.02] text-[#71717A] text-xs">
                    No internal importers found (root entrypoint, page, or isolated test).
                  </div>
                ) : (
                  <div className="divide-y divide-white/5 border border-white/10 rounded-lg overflow-hidden bg-black/20">
                    {neighborsState.importedBy.map((src) => {
                      const srcExt = src.includes(".") ? `.${src.split(".").pop()}` : "";
                      const srcStyle = getLanguageStyle(srcExt, false);
                      return (
                        <div
                          key={src}
                          className="flex items-center justify-between p-2.5 hover:bg-white/[0.04] transition-colors group"
                        >
                          <div className="flex items-center gap-2.5 min-w-0">
                            <span
                              className="font-mono text-[9px] font-bold px-1.5 py-0.5 rounded text-white flex-shrink-0"
                              style={{ backgroundColor: srcStyle.bg, color: srcStyle.text }}
                            >
                              {srcStyle.label}
                            </span>
                            <div className="flex flex-col min-w-0">
                              <span className="text-white text-xs font-semibold truncate group-hover:text-emerald-400 transition-colors">
                                {src.split("/").pop()}
                              </span>
                              <span className="text-[10px] text-[#71717A] truncate">{src}</span>
                            </div>
                          </div>

                          {onSelectNode && (
                            <button
                              type="button"
                              onClick={() => onSelectNode(src)}
                              title={`Focus ${src} in Atlas`}
                              className="px-2 py-1 rounded bg-white/5 hover:bg-emerald-500/20 text-[#A1A1AA] hover:text-emerald-300 border border-white/10 hover:border-emerald-500/30 text-[10px] font-mono flex items-center gap-1 transition-all cursor-pointer flex-shrink-0"
                            >
                              <span>Focus</span>
                              <span>↗</span>
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

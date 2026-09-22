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
}

interface FileContentState {
  status: "loading" | "ready" | "error" | "binary";
  content?: string;
  error?: string;
}

export function CodePreviewPanel({
  repoId,
  selection,
  activeIncidents = [],
  commitSha = "HEAD",
  onClose,
}: CodePreviewPanelProps) {
  const { nodeId, brokenBy, node } = selection;
  const isBinary = node?.is_binary ?? false;
  const ext = node?.ext ?? "";
  const langStyle = getLanguageStyle(ext, isBinary);

  const [state, setState] = useState<FileContentState>(
    isBinary ? { status: "binary" } : { status: "loading" }
  );

  useEffect(() => {
    if (isBinary) {
      setState({ status: "binary" });
      return;
    }

    let isMounted = true;
    setState({ status: "loading" });

    const params = new URLSearchParams({
      path: nodeId,
      ref: commitSha,
    });

    fetch(`${API_BASE}/api/repos/${repoId}/atlas/file?${params}`, {
      credentials: "include",
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
          setState({ status: "binary" });
        } else {
          setState({ status: "ready", content: data.content });
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        setState({ status: "error", error: err.message || "Failed to load content." });
      });

    return () => {
      isMounted = false;
    };
  }, [repoId, nodeId, commitSha, isBinary]);

  // Implicated incidents
  const incidentDetails = useMemo(() => {
    if (brokenBy.length === 0) return [];
    return activeIncidents.filter((inc) => brokenBy.includes(inc.detected_change_id));
  }, [brokenBy, activeIncidents]);

  return (
    <div
      role="dialog"
      aria-label={`Code preview for ${node?.name || nodeId}`}
      className="fixed inset-y-0 right-0 w-full sm:w-[560px] z-50 bg-[#050507]/95 backdrop-blur-2xl border-l border-white/10 flex flex-col shadow-[-16px_0_48px_rgba(0,0,0,0.85)] animate-in slide-in-from-right duration-200"
    >
      {/* Top Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-white/10 bg-black/40">
        <div className="flex items-center gap-3 min-w-0">
          <span
            className="font-mono text-xs font-bold px-2 py-0.5 rounded text-white flex-shrink-0"
            style={{ backgroundColor: langStyle.bg, color: langStyle.text }}
          >
            {langStyle.label}
          </span>
          <div className="flex flex-col min-w-0">
            <h2 className="font-mono text-sm font-semibold text-white truncate tracking-tight">
              {node?.name || nodeId.split("/").pop()}
            </h2>
            <span className="font-mono text-[11px] text-[#71717A] truncate">
              {nodeId}
            </span>
          </div>
        </div>

        <button
          onClick={onClose}
          aria-label="Close code preview panel"
          className="font-mono text-xs w-8 h-8 rounded-lg border border-white/15 bg-white/5 text-[#A1A1AA] hover:text-white hover:border-white/30 flex items-center justify-center transition-all cursor-pointer flex-shrink-0"
        >
          ✕
        </button>
      </div>

      {/* Breakage Notice Banner (Red overlay strictly for active incidents) */}
      {brokenBy.length > 0 && (
        <div className="px-5 py-3 bg-[#E11D48]/10 border-b border-[#E11D48]/30 flex flex-col gap-1.5">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#E11D48] animate-pulse" />
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
                <span className="text-[#5EEAD4]">{inc.symbol_new || "removed"}</span>
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
        <div className="px-5 py-2.5 bg-white/[0.02] border-b border-white/5 flex flex-col gap-1">
          <span className="font-mono text-[10px] text-[#A1A1AA] flex items-center gap-1.5">
            <span>⚠</span> {node.unresolved_import_count} unresolved / dynamic static specifier(s):
          </span>
          <div className="flex flex-wrap gap-1.5 pl-4">
            {node.unresolved_specifiers.map((spec, i) => (
              <code
                key={i}
                className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-[#71717A]"
              >
                {spec}
              </code>
            ))}
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 overflow-auto p-5 font-mono text-xs leading-relaxed select-text">
        {state.status === "loading" && (
          <div className="h-64 flex flex-col items-center justify-center gap-3">
            <div className="w-7 h-7 border border-white/20 border-t-white/70 rounded-full animate-spin" />
            <span className="font-mono text-xs text-[#71717A]">Fetching file content…</span>
          </div>
        )}

        {state.status === "binary" && (
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

        {state.status === "error" && (
          <div className="h-64 flex flex-col items-center justify-center gap-3 text-center px-4">
            <span className="font-mono text-xs text-[#E5A93C]">Unable to load file content</span>
            <p className="font-mono text-[11px] text-[#71717A]">{state.error}</p>
          </div>
        )}

        {state.status === "ready" && state.content && (
          <div className="relative">
            <pre className="text-xs leading-5 text-[#E4E4E7] font-mono whitespace-pre overflow-x-auto tab-4">
              {state.content.split("\n").map((line, idx) => (
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
    </div>
  );
}

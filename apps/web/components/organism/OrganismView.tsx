"use client";

import "./OrganismView.css";

/**
 * OrganismView — 3D physics-simulated incident graph.
 *
 * Usage:
 *   <OrganismView dataSource={new FixtureDataSource()} />          // marketing
 *   <OrganismView dataSource={new DashboardDataSource(repoId, changeId)} showHUD />
 *
 * Pattern mirrors TelexBot3D.tsx exactly (raw imperative Three.js in useEffect,
 * strict GPU disposal on unmount). No React Three Fiber.
 */

import { useEffect, useRef, useState } from "react";
import type { OrganismDataSource } from "./types";
import type { IncidentEvent, IncidentGraph } from "./types";
import { OrganismScene } from "./OrganismScene";
import { NODE_STATUS } from "./NodeRenderer";

interface OrganismViewProps {
  dataSource: OrganismDataSource;
  /** Show the HUD overlay (legend, stats). False on marketing embeds. */
  showHUD?: boolean;
  className?: string;
}

type Status = "loading" | "live" | "error";

export default function OrganismView({
  dataSource,
  showHUD = false,
  className = "",
}: OrganismViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<OrganismScene | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [graph, setGraph] = useState<IncidentGraph | null>(null);
  const [activeCount, setActiveCount] = useState(0);
  const [resolvedCount, setResolvedCount] = useState(0);

  useEffect(() => {
    if (!containerRef.current) return;
    let unsubscribe: (() => void) | null = null;
    let destroyed = false;
    const container = containerRef.current;

    (async () => {
      try {
        const snapshot = await dataSource.fetchSnapshot();
        if (destroyed) return;

        setGraph(snapshot);
        setActiveCount(snapshot.nodes.length);
        setStatus("live");

        const scene = new OrganismScene(container);
        scene.init(snapshot);
        sceneRef.current = scene;

        unsubscribe = dataSource.subscribe((event: IncidentEvent) => {
          if (destroyed || !sceneRef.current) return;
          handleEvent(event, sceneRef.current, setActiveCount, setResolvedCount);
        });
      } catch (err) {
        if (!destroyed) {
          console.error("OrganismView: failed to init", err);
          setStatus("error");
        }
      }
    })();

    return () => {
      destroyed = true;
      unsubscribe?.();
      sceneRef.current?.destroy();
      sceneRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      className={`relative w-full h-full ${className}`}
      style={{ minHeight: 420 }}
    >
      {/* Three.js canvas mount target */}
      <div ref={containerRef} className="absolute inset-0" />

      {/* Loading state */}
      {status === "loading" && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="organism-loading">
            <span className="organism-loading-dot" />
            <span className="organism-loading-dot" />
            <span className="organism-loading-dot" />
          </div>
        </div>
      )}

      {/* Error state */}
      {status === "error" && (
        <div className="absolute inset-0 flex items-center justify-center">
          <p className="organism-error-text">[ INCIDENT DATA UNAVAILABLE ]</p>
        </div>
      )}

      {/* HUD overlay */}
      {showHUD && status === "live" && graph && (
        <OrganismHUD
          graph={graph}
          activeCount={activeCount}
          resolvedCount={resolvedCount}
        />
      )}

      {/* Drag hint */}
      {status === "live" && (
        <p className="organism-drag-hint">drag to orbit · scroll to zoom</p>
      )}
    </div>
  );
}

// ── Event → scene bridge ──────────────────────────────────────────────────────

function handleEvent(
  event: IncidentEvent,
  scene: OrganismScene,
  setActiveCount: (fn: (n: number) => number) => void,
  setResolvedCount: (fn: (n: number) => number) => void
) {
  const cu = event.code_usage_id;
  const payload = event.payload ?? {};

  switch (event.event_type) {
    case "usage_found":
      scene.addNode({
        code_usage_id: cu!,
        file_path: (payload.file_path as string) ?? "",
        line_start: (payload.line_start as number) ?? 0,
        line_end: (payload.line_end as number) ?? 0,
        status: "pending",
      });
      setActiveCount((n) => n + 1);
      break;

    case "patch_generated":
      if (cu) {
        scene.updateNodeStatus(cu, "pending");
        scene.setPulse(cu, "out");
      }
      break;

    case "patch_failed":
      if (cu) {
        scene.updateNodeStatus(cu, "failed");
      }
      break;

    case "validating":
      if (cu) {
        scene.setPulse(cu, "in");
      }
      break;

    case "validation_passed":
      if (cu) {
        scene.updateNodeValidation(cu, true);
        scene.setPulse(cu, "out");
      }
      break;

    case "validation_failed":
      if (cu) {
        scene.updateNodeValidation(cu, false);
      }
      break;

    case "pr_opened":
      // Resolve all verified nodes to the calm outer ring
      scene.nodes.forEach((sn, id) => {
        if (sn.meta.status === "patched" || sn.resolved) {
          scene.resolveNode(id);
          setResolvedCount((n) => n + 1);
          setActiveCount((n) => Math.max(0, n - 1));
        }
      });
      break;

    case "job_running":
    case "job_done":
      scene.triggerSceneAmbience();
      break;

    case "change_detected":
      // Root node already exists — just pulse scene ambience
      scene.triggerSceneAmbience();
      break;
  }
}

// ── HUD Component ─────────────────────────────────────────────────────────────

interface HUDProps {
  graph: IncidentGraph;
  activeCount: number;
  resolvedCount: number;
}

function OrganismHUD({ graph, activeCount, resolvedCount }: HUDProps) {
  return (
    <>
      {/* Top-left: incident header */}
      <div className="organism-hud-panel organism-hud-topleft">
        <p className="organism-hud-label">INCIDENT</p>
        <p className="organism-hud-title">
          <span className="organism-amber">{graph.package}</span>
        </p>
        <p className="organism-hud-sub">
          {graph.symbol_old}
          {graph.symbol_new ? ` → ${graph.symbol_new}` : ""}
        </p>
        <p className="organism-hud-badge">
          {(graph.confidence * 100).toFixed(0)}% confidence
        </p>
      </div>

      {/* Top-right: stats */}
      <div className="organism-hud-panel organism-hud-topright">
        <div className="organism-stat">
          <span className="organism-stat-num">{activeCount}</span>
          <span className="organism-stat-label">ACTIVE</span>
        </div>
        <div className="organism-stat">
          <span className="organism-stat-num organism-teal">{resolvedCount}</span>
          <span className="organism-stat-label">RESOLVED</span>
        </div>
      </div>

      {/* Bottom-left: legend */}
      <div className="organism-hud-panel organism-hud-bottomleft">
        <div className="organism-legend-row">
          <span className="organism-dot organism-dot-amber" />
          <span>Generating</span>
        </div>
        <div className="organism-legend-row">
          <span className="organism-dot organism-dot-teal" />
          <span>Verified / PR opened</span>
        </div>
        <div className="organism-legend-row">
          <span className="organism-dot organism-dot-dim" />
          <span>Pending review</span>
        </div>
        <p className="organism-brand-note">Telex never auto-merges.</p>
      </div>
    </>
  );
}

"use client";

import React from "react";

interface CyberSkeletonProps {
  className?: string;
  variant?: "rect" | "circle" | "text";
}

/**
 * Base monochrome skeleton primitive with laser shimmer sheen.
 */
export function CyberSkeleton({
  className = "",
  variant = "rect",
}: CyberSkeletonProps) {
  const variantClasses = {
    rect: "rounded-lg",
    circle: "rounded-full",
    text: "rounded h-3 my-1",
  }[variant];

  return (
    <div
      aria-hidden="true"
      className={`animate-shimmer bg-white/[0.04] border border-white/[0.06] ${variantClasses} ${className}`}
    />
  );
}

/**
 * Container card skeleton with subtle backdrop and border.
 */
export function CyberSkeletonCard({
  children,
  className = "",
}: {
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`metal-bezel p-[2px] ${className}`}>
      <div className="panel-inset p-5 rounded-[6px] flex flex-col gap-4 animate-shimmer relative overflow-hidden">
        {children}
      </div>
    </div>
  );
}

/**
 * Metric strip skeleton matching the 4-column telemetry bar.
 */
export function CyberSkeletonMetric() {
  return (
    <div className="metal-bezel p-[2px]">
      <div className="panel-inset grid grid-cols-2 md:grid-cols-4 rounded-[6px] divide-y md:divide-y-0 md:divide-x divide-black/80 shadow-lg animate-shimmer">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="p-4 flex flex-col gap-2">
            <CyberSkeleton className="w-24 h-3 bg-white/[0.05]" />
            <div className="flex items-baseline gap-2 mt-1">
              <CyberSkeleton className="w-16 h-7 bg-white/[0.08]" />
              <CyberSkeleton className="w-12 h-2.5 bg-white/[0.04]" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Repository card skeleton matching RepoCard / ReposPage listing.
 */
export function CyberSkeletonRepo() {
  return (
    <div className="metal-bezel p-[2px]">
      <div className="panel-inset p-5 rounded-[6px] flex items-center justify-between gap-4 animate-shimmer">
        <div className="flex items-center gap-4 flex-1">
          <CyberSkeleton variant="circle" className="w-2.5 h-2.5 flex-shrink-0 bg-white/20" />
          <div className="flex flex-col gap-2 flex-1 max-w-sm">
            <div className="flex items-center gap-2">
              <CyberSkeleton className="w-20 h-4 bg-white/[0.05]" />
              <CyberSkeleton className="w-32 h-4 bg-white/[0.08]" />
            </div>
            <CyberSkeleton className="w-48 h-2.5 bg-white/[0.04]" />
          </div>
        </div>
        <div className="flex items-center gap-3">
          <CyberSkeleton className="w-20 h-6 rounded-full bg-white/[0.05]" />
          <CyberSkeleton className="w-16 h-7 rounded-lg bg-white/[0.08]" />
        </div>
      </div>
    </div>
  );
}

/**
 * Activity feed item skeleton matching the timeline events.
 */
export function CyberSkeletonActivity() {
  return (
    <div className="metal-bezel p-[2px]">
      <div className="panel-inset p-4 rounded-[6px] flex flex-col sm:flex-row sm:items-center justify-between gap-3 animate-shimmer">
        <div className="flex items-start sm:items-center gap-3.5 flex-1">
          <CyberSkeleton variant="circle" className="w-8 h-8 flex-shrink-0 bg-white/[0.06]" />
          <div className="flex flex-col gap-1.5 flex-1">
            <div className="flex items-center gap-2">
              <CyberSkeleton className="w-24 h-4 bg-white/[0.07]" />
              <CyberSkeleton className="w-16 h-3 bg-white/[0.04]" />
            </div>
            <CyberSkeleton className="w-64 max-w-full h-3 bg-white/[0.04]" />
          </div>
        </div>
        <div className="flex items-center gap-2.5 self-end sm:self-center">
          <CyberSkeleton className="w-28 h-6 rounded-md bg-white/[0.05]" />
        </div>
      </div>
    </div>
  );
}


/**
 * Detailed patch viewer skeleton for /dashboard/repos/[id].
 */
export function CyberSkeletonPatch() {
  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto w-full animate-shimmer">
      {/* Breadcrumb & Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-1">
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <CyberSkeleton className="w-24 h-3 bg-white/[0.05]" />
            <span className="text-[#3F3F46]">/</span>
            <CyberSkeleton className="w-24 h-3 bg-white/[0.05]" />
            <span className="text-[#3F3F46]">/</span>
            <CyberSkeleton className="w-32 h-3 bg-white/[0.08]" />
          </div>
          <CyberSkeleton className="w-64 h-8 bg-white/[0.1] rounded-lg" />
        </div>
        <div className="flex items-center gap-3">
          <CyberSkeleton className="w-32 h-8 rounded-lg bg-white/[0.08]" />
          <CyberSkeleton className="w-24 h-8 rounded-lg bg-white/[0.06]" />
        </div>
      </div>

      {/* Verification & Gate Badges Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {[...Array(3)].map((_, i) => (
          <div
            key={i}
            className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.06] flex flex-col gap-1.5"
          >
            <CyberSkeleton className="w-20 h-2.5 bg-white/[0.04]" />
            <CyberSkeleton className="w-36 h-4 bg-white/[0.07]" />
          </div>
        ))}
      </div>

      {/* Split Pane: Tickets on Left, Diff on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left Rail: Ticket List */}
        <div className="lg:col-span-4 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <CyberSkeleton className="w-28 h-3.5 bg-white/[0.06]" />
            <CyberSkeleton className="w-12 h-3.5 bg-white/[0.04]" />
          </div>
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="p-3.5 rounded-xl border border-white/10 bg-black/60 flex flex-col gap-2"
            >
              <div className="flex items-center justify-between">
                <CyberSkeleton className="w-28 h-4 bg-white/[0.08]" />
                <CyberSkeleton className="w-14 h-4 rounded-full bg-white/[0.05]" />
              </div>
              <CyberSkeleton className="w-36 h-3 bg-white/[0.04]" />
              <CyberSkeleton className="w-20 h-2.5 bg-white/[0.03]" />
            </div>
          ))}
        </div>

        {/* Right Pane: Synthesized Unified Diff */}
        <div className="lg:col-span-8 flex flex-col gap-3">
          <div className="metal-bezel p-[2px]">
            <div className="panel-inset p-4 rounded-[6px] flex flex-col gap-3">
              <div className="flex items-center justify-between pb-3 border-b border-black/80 shadow-[0_1px_0_rgba(255,255,255,0.05)]">
                <CyberSkeleton className="w-48 h-4 bg-white/[0.08]" />
                <CyberSkeleton className="w-28 h-4 bg-white/[0.05]" />
              </div>
              {/* Diff Lines Wireframe */}
              <div className="flex flex-col gap-1 font-mono">
                <CyberSkeleton className="w-full h-4 bg-white/[0.02]" />
                <CyberSkeleton className="w-3/4 h-4 bg-white/[0.04]" />
                <CyberSkeleton className="w-5/6 h-4 bg-white/[0.06]" />
                <CyberSkeleton className="w-4/5 h-4 bg-white/[0.04]" />
                <CyberSkeleton className="w-2/3 h-4 bg-white/[0.03]" />
                <CyberSkeleton className="w-3/4 h-4 bg-white/[0.05]" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * High-tech animated radar scanner graphic.
 */
export function CyberRadarScanner({
  label = "Scanning telemetry…",
  subtext = "Autonomous daemon analyzing call sites and verification logs",
}: {
  label?: string;
  subtext?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center relative overflow-hidden">
      {/* Concentric Radar Rings */}
      <div className="relative w-28 h-28 flex items-center justify-center mb-5">
        <div className="absolute inset-0 rounded-full border border-white/10 animate-ping opacity-25" />
        <div className="absolute inset-2 rounded-full border border-white/20 animate-pulse" />
        <div className="absolute inset-6 rounded-full border border-white/30" />
        {/* Rotating sweep line */}
        <div className="absolute inset-0 rounded-full border border-dashed border-white/40 animate-spin [animation-duration:8s]" />
        <span className="led" data-state="ok" style={{ width: "10px", height: "10px" }} />
      </div>

      <div className="flex items-center gap-2 mb-1.5">
        <span className="led" data-state="ok" />
        <span className="label-engraved text-xs text-white">
          {label}
        </span>
      </div>
      <p className="font-mono text-[11px] text-[#A1A1AA] max-w-sm leading-relaxed">
        {subtext}
      </p>
    </div>
  );
}


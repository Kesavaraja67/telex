"use client";

import Link from "next/link";
import { motion } from "motion/react";
import Badge from "@/components/ui/Badge";
import SpotlightCard from "@/components/ui/SpotlightCard";
import type { RecoveryEvent } from "@/lib/api";

interface RecoveryTicketProps {
  event: RecoveryEvent;
}

// Map Engine B outcome/classification to existing Badge statuses
function outcomeToBadgeStatus(outcome: string): "open" | "merged" | "closed" | "pending" | "patched" | "failed" {
  if (outcome === "recovered") return "patched";
  if (outcome === "escalated") return "open";
  if (outcome === "unresolved") return "closed";
  return "pending";
}

// Derive tier label from action_taken prefix (set deterministically by diagnose_runtime_failure.py)
function getTierLabel(actionTaken: string): { label: string; color: string } {
  if (actionTaken.startsWith("Classified via deterministic rule")) {
    return { label: "RULE", color: "#FFFFFF" };
  }
  if (actionTaken.startsWith("Classified via LLM")) {
    return { label: "LLM", color: "#A1A1AA" };
  }
  return { label: "SYS", color: "#71717A" };
}

const inrFormatter = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

export default function RecoveryTicket({ event }: RecoveryTicketProps) {
  const timeAgo = (() => {
    const diff = Date.now() - new Date(event.detected_at).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  })();

  const tier = getTierLabel(event.action_taken);
  const isDeliberateStop = event.action_taken.startsWith("Stopped retrying");
  const badgeStatus = outcomeToBadgeStatus(event.outcome);

  // Derive attempt number if mentioned
  const attemptMatch = event.action_taken.match(/after (\d+) attempts?/);
  const attemptCount = attemptMatch ? Number(attemptMatch[1]) : (event.outcome === "recovered" ? 1 : null);

  return (
    <SpotlightCard
      spotlightColor="rgba(255, 255, 255, 0.08)"
      enableTilt={false}
      className="p-0 border-white/[0.08] hover:border-white/20 bg-black/70 backdrop-blur-xl transition-all"
    >
      <div className="px-5 pt-4 pb-3 flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1.5 min-w-0">
          <div className="flex items-center gap-2.5 flex-wrap">
            {/* Tier label — RULE (deterministic) vs LLM (model-classified) */}
            <span
              className="font-mono text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded border border-white/10"
              style={{ color: tier.color, backgroundColor: "rgba(255, 255, 255, 0.06)" }}
            >
              {tier.label}
            </span>
            <span className="font-mono font-semibold text-sm text-white tracking-tight">
              {event.failure_type}
            </span>
            <span className="font-mono text-xs text-[#A1A1AA]">
              / <span className="text-white font-medium">{event.classification}</span>
            </span>
            {event.amount ? (
              <span className="font-mono text-xs font-semibold text-white px-2 py-0.5 rounded bg-white/10 border border-white/20">
                {inrFormatter.format(event.amount / 100)}
              </span>
            ) : null}
          </div>
          <div className="font-mono text-[11px] text-[#A1A1AA] max-w-xl truncate">
            {event.action_taken.split(": ").slice(1).join(": ") || event.action_taken}
          </div>
        </div>
        <div className="flex items-center gap-2.5 flex-shrink-0">
          {attemptCount !== null && (
            <span className="font-mono text-[10px] text-[#A1A1AA] border border-white/10 px-2 py-0.5 rounded bg-white/[0.02]">
              Attempt #{attemptCount}
            </span>
          )}
          {isDeliberateStop ? (
            <span className="font-mono text-[10px] uppercase font-semibold px-2 py-0.5 rounded bg-white/10 text-white border border-white/25">
              STOPPED (2/2)
            </span>
          ) : (
            <Badge status={badgeStatus} />
          )}
          <span suppressHydrationWarning className="font-mono text-[10px] text-[#71717A]">{timeAgo}</span>
        </div>
      </div>

      <div className="px-5 py-2.5 flex items-center justify-between gap-4 border-t border-white/[0.06] bg-white/[0.01]">
        <div className="flex items-center gap-2">
          {event.outcome === "escalated" && (
            <span className="font-mono text-xs text-white flex items-center gap-1.5 font-medium">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              <span>{event.pull_request_id ? "PR OPENED — PATCH VERIFIED" : "PR PIPELINE QUEUED — GENERATING PATCH"}</span>
            </span>
          )}
          {event.outcome === "recovered" && (
            <span className="font-mono text-xs text-white flex items-center gap-1.5 font-medium">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
              </svg>
              <span>RETRY SUCCEEDED (AUTO-RESOLVED)</span>
            </span>
          )}
          {event.outcome === "unresolved" && (
            <span
              className="font-mono text-xs text-[#A1A1AA]"
            >
              {isDeliberateStop
                ? "DELIBERATE STOP — REPEATED CARD DECLINE HALTED"
                : "RETRY FAILED — MANUAL REVIEW REQUIRED"}
            </span>
          )}
        </div>
        <span className="font-mono text-[10px] text-[#71717A]">
          {event.llm_provider !== "none" ? `via ${event.llm_model}` : "deterministic (0 tokens)"}
        </span>
      </div>
    </SpotlightCard>
  );
}

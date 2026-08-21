"use client";

import Link from "next/link";
import Badge from "@/components/ui/Badge";
import type { RecoveryEvent } from "@/lib/api";

interface RecoveryTicketProps {
  event: RecoveryEvent;
}

// Map Engine B outcome/classification to existing Badge statuses — no new badge variants
function outcomeToBadgeStatus(outcome: string): "open" | "merged" | "closed" | "pending" | "patched" | "failed" {
  if (outcome === "recovered") return "patched";
  if (outcome === "escalated") return "open";
  if (outcome === "unresolved") return "closed";
  return "pending";
}

// Derive tier label from action_taken prefix (set deterministically by diagnose_runtime_failure.py)
function getTierLabel(actionTaken: string): { label: string; color: string } {
  if (actionTaken.startsWith("Classified via deterministic rule")) {
    return { label: "RULE", color: "#4FD1C5" };
  }
  if (actionTaken.startsWith("Classified via LLM")) {
    return { label: "LLM", color: "#A78BFA" };
  }
  return { label: "—", color: "#7A7F87" };
}

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
  const badgeStatus = outcomeToBadgeStatus(event.outcome);

  return (
    <div
      className="glass-surface w-full transition-all hover:border-white/20 bg-black/60 backdrop-blur-xl"
      style={{ opacity: 1, transform: "none" }}
    >
      <div className="px-5 pt-4 pb-2.5 flex items-start justify-between gap-2">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2.5">
            {/* Tier label — RULE (deterministic) vs LLM (model-classified) */}
            <span
              className="font-mono text-[10px] px-1.5 py-0.5 rounded border border-white/10"
              style={{ color: tier.color, backgroundColor: `${tier.color}14` }}
            >
              {tier.label}
            </span>
            <span className="font-mono font-semibold text-sm text-white">
              {event.failure_type}
            </span>
            <span className="font-mono text-xs text-[#8B9099]">
              → <span className="text-white">{event.classification}</span>
            </span>
          </div>
          <div className="font-mono text-[11px] text-[#8B9099] max-w-md truncate">
            {event.action_taken.split(": ").slice(1).join(": ") || event.action_taken}
          </div>
        </div>
        <div className="flex items-center gap-2.5 flex-shrink-0">
          <Badge status={badgeStatus} />
          <span className="font-mono text-[10px] text-[#8B9099]">{timeAgo}</span>
        </div>
      </div>

      <div className="px-5 py-2.5 flex items-center gap-4 border-t border-white/[0.06] bg-white/[0.01]">
        {event.outcome === "escalated" && event.pull_request_id && (
          <span className="font-mono text-xs text-[#8B9099]">
            PR enqueued — generate_patch running
          </span>
        )}
        {event.outcome === "recovered" && (
          <span className="font-mono text-xs text-[#4FD1C5]">
            ✓ Retry succeeded
          </span>
        )}
        {event.outcome === "unresolved" && (
          <span className="font-mono text-xs text-[#8B9099]">
            Retry failed — manual investigation required
          </span>
        )}
        <span className="font-mono text-[10px] text-[#8B9099] ml-auto">
          {event.llm_provider !== "none" ? `via ${event.llm_model}` : "no LLM call"}
        </span>
      </div>
    </div>
  );
}

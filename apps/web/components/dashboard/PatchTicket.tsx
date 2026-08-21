"use client";

import Link from "next/link";
import Badge from "@/components/ui/Badge";
import type { PatchSummary } from "@/lib/api";

interface PatchTicketProps {
  patch: PatchSummary;
  repoId?: string;
}

export default function PatchTicket({ patch, repoId }: PatchTicketProps) {
  const timeAgo = (() => {
    const diff = Date.now() - new Date(patch.opened_at).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  })();

  return (
    <div
      className="glass-surface w-full transition-all hover:border-white/20 bg-black/60 backdrop-blur-xl"
      style={{ opacity: 1, transform: "none" }}
    >
      <div className="px-5 pt-4 pb-2.5 flex items-start justify-between gap-2">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2.5">
            <span className="font-mono text-[10px] text-[#8B9099] bg-white/[0.04] px-1.5 py-0.5 rounded">
              PATCH
            </span>
            <span className="font-mono font-semibold text-sm text-white">
              {patch.package}
            </span>
            <span className="font-mono text-xs text-[#8B9099]">
              → <span className="text-white">{patch.new_version}</span>
            </span>
          </div>
          <div className="font-mono text-[11px] text-[#8B9099]">
            {patch.usages_patched} call site{patch.usages_patched !== 1 ? "s" : ""} auto-patched
          </div>
        </div>
        <div className="flex items-center gap-2.5 flex-shrink-0">
          <Badge status={patch.status} />
          <span className="font-mono text-[10px] text-[#8B9099]">{timeAgo}</span>
        </div>
      </div>

      <div
        className="px-5 py-2.5 flex items-center gap-4 border-t border-white/[0.06] bg-white/[0.01]"
      >
        {patch.pr_url && (
          <Link
            href={patch.pr_url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-mono text-xs hover:underline text-white font-medium flex items-center gap-1"
          >
            View GitHub PR →
          </Link>
        )}
        {repoId && (
          <Link
            href={`/dashboard/repos/${repoId}`}
            className="font-mono text-xs text-[#8B9099] hover:text-white transition-colors"
          >
            Inspect diff
          </Link>
        )}
      </div>
    </div>
  );
}

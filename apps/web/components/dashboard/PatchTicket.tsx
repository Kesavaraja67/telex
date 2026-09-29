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
    <div className="metal-bezel p-[2px] w-full transition-all hover:brightness-105">
      <div className="panel-inset rounded-[6px] overflow-hidden">
        <div className="px-5 pt-4 pb-3 flex items-start justify-between gap-2">
          <div className="flex flex-col gap-1.5 min-w-0">
            <div className="flex items-center gap-2.5 flex-wrap">
              <span className="label-engraved bg-black/60 px-2 py-0.5 rounded border border-black/80 shadow-[inset_0_1px_3px_rgba(0,0,0,0.8),0_1px_0_rgba(255,255,255,0.05)] text-[10px]">
                PATCH
              </span>
              <span className="font-mono font-bold text-sm text-white label-embossed">
                {patch.package}
              </span>
              <span className="font-mono text-xs text-[#8B9099]">
                → <span className="text-white font-semibold">{patch.new_version}</span>
              </span>
            </div>
            <div className="font-mono text-[11px] text-[#6b7280]">
              <span className="text-white font-medium">{patch.usages_patched}</span> call site{patch.usages_patched !== 1 ? "s" : ""} auto-patched
            </div>
          </div>
          <div className="flex items-center gap-2.5 flex-shrink-0">
            <Badge status={patch.status} />
            <span suppressHydrationWarning className="font-mono text-[10px] text-[#6b7280]">{timeAgo}</span>
          </div>
        </div>

        <div className="px-5 py-2.5 flex items-center gap-4 border-t border-black/70 shadow-[0_1px_0_rgba(255,255,255,0.05)] bg-black/25">
          {patch.pr_url && (
            <Link
              href={patch.pr_url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-xs hover:text-white text-[#d4d4d8] font-medium flex items-center gap-1 transition-colors"
            >
              View GitHub PR →
            </Link>
          )}
          {repoId && (
            <Link
              href={`/dashboard/repos/${repoId}`}
              className="font-mono text-xs text-[#6b7280] hover:text-white transition-colors"
            >
              Inspect diff
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}


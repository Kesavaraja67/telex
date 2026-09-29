"use client";

import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import type { Repo } from "@/lib/api";

interface RepoCardProps {
  repo: Repo;
  patchCount?: number;
  onToggle?: (id: string, newState: boolean) => void;
}

export default function RepoCard({ repo, patchCount = 0, onToggle }: RepoCardProps) {
  const [owner, name] = repo.full_name.split("/");

  return (
    <div className="metal-bezel p-[2px] rounded-xl transition-all hover:brightness-105 relative">
      {/* Decorative machined corner rivets */}
      <span className="absolute top-2 left-2 w-1.5 h-1.5 rounded-full bg-[#3F3F46] shadow-[inset_0_1px_1px_rgba(255,255,255,0.3),0_1px_0_rgba(0,0,0,0.8)] z-10 pointer-events-none" />
      <span className="absolute top-2 right-2 w-1.5 h-1.5 rounded-full bg-[#3F3F46] shadow-[inset_0_1px_1px_rgba(255,255,255,0.3),0_1px_0_rgba(0,0,0,0.8)] z-10 pointer-events-none" />
      <span className="absolute bottom-2 left-2 w-1.5 h-1.5 rounded-full bg-[#3F3F46] shadow-[inset_0_1px_1px_rgba(255,255,255,0.3),0_1px_0_rgba(0,0,0,0.8)] z-10 pointer-events-none" />
      <span className="absolute bottom-2 right-2 w-1.5 h-1.5 rounded-full bg-[#3F3F46] shadow-[inset_0_1px_1px_rgba(255,255,255,0.3),0_1px_0_rgba(0,0,0,0.8)] z-10 pointer-events-none" />

      <div className="panel-inset p-5 rounded-[10px] flex items-center justify-between gap-4">
        <div className="flex items-center gap-4 min-w-0">
          {/* Active status dome LED */}
          <span
            className="led"
            data-state={repo.is_active ? "ok" : "off"}
            title={repo.is_active ? "Active Monitoring" : "Monitoring Inactive"}
            aria-label={repo.is_active ? "Active" : "Inactive"}
          />

          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono text-xs text-[#71717a]">{owner}/</span>
              <span className="font-mono font-bold text-sm text-[#f4f4f5] tracking-wide label-embossed">
                {name}
              </span>
            </div>
            <div className="font-sans text-xs text-[#8B9099] mt-0.5 flex items-center gap-3">
              <span>
                Default branch: <span className="text-[#d4d4d8] font-mono">{repo.default_branch}</span>
              </span>
              {patchCount > 0 && (
                <span className="font-mono text-[11px] text-[#71717a]">
                  <span className="text-white font-semibold">{patchCount}</span> patches
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 flex-shrink-0">
          <Badge status={repo.is_active ? "patched" : "closed"} />
          <Button
            id={`repo-toggle-${repo.id}`}
            variant={repo.is_active ? "ghost" : "primary"}
            size="sm"
            onClick={() => onToggle?.(repo.id, !repo.is_active)}
          >
            {repo.is_active ? "Pause" : "Watch"}
          </Button>
        </div>
      </div>
    </div>
  );
}


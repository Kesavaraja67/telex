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
    <div
      className="glass-surface p-5 flex items-center justify-between gap-4 transition-all hover:border-white/20 bg-black/60 backdrop-blur-xl"
    >
      <div className="flex items-center gap-4">
        {/* Active indicator */}
        <div
          className="w-2 h-2 rounded-full flex-shrink-0 transition-colors"
          style={{ background: repo.is_active ? "#FFFFFF" : "#555555" }}
        />

        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-[#8B9099]">{owner}/</span>
            <span className="font-mono font-semibold text-sm text-white">{name}</span>
          </div>
          <div className="font-sans text-xs text-[#8B9099] mt-0.5">
            Default branch: <span className="text-white font-mono">{repo.default_branch}</span>
            {patchCount > 0 && (
              <span className="ml-3 font-mono">
                <span className="text-white font-semibold">{patchCount}</span> patches
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Badge status={repo.is_active ? "patched" : "closed"} />
        <Button
          id={`repo-toggle-${repo.id}`}
          variant={repo.is_active ? "ghost" : "primary"}
          size="sm"
          className="rounded-full text-xs px-4 py-1 font-mono border-white/20 hover:border-white/40 text-white"
          onClick={() => onToggle?.(repo.id, !repo.is_active)}
        >
          {repo.is_active ? "Pause" : "Watch"}
        </Button>
      </div>
    </div>
  );
}

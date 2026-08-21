import type { Metadata } from "next";
import RepoCard from "@/components/dashboard/RepoCard";
import Button from "@/components/ui/Button";
import type { Repo } from "@/lib/api";

export const metadata: Metadata = { title: "Dashboard — Repos" };

const DEMO_REPOS: Repo[] = [
  {
    id: "r1",
    full_name: "acme/api-server",
    default_branch: "main",
    is_active: true,
    created_at: new Date().toISOString(),
  },
  {
    id: "r2",
    full_name: "acme/frontend",
    default_branch: "main",
    is_active: true,
    created_at: new Date().toISOString(),
  },
  {
    id: "r3",
    full_name: "acme/data-pipeline",
    default_branch: "develop",
    is_active: false,
    created_at: new Date().toISOString(),
  },
];

export default function ReposPage() {
  return (
    <div className="flex flex-col gap-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-mono font-bold text-2xl text-text" style={{ letterSpacing: "-0.02em" }}>
            Watched repos
          </h1>
          <p className="font-sans text-sm mt-1" style={{ color: "var(--muted)" }}>
            Connect repos to start watching their dependencies.
          </p>
        </div>
        <Button id="install-telex-btn" variant="primary" size="md">
          Install Telex →
        </Button>
      </div>

      {/* Repos list */}
      {DEMO_REPOS.length > 0 ? (
        <div className="flex flex-col gap-3">
          {DEMO_REPOS.map((repo) => (
            <RepoCard key={repo.id} repo={repo} patchCount={6} />
          ))}
        </div>
      ) : (
        /* Empty state — invitation, not apology (Appendix F) */
        <div
          className="rounded-lg p-12 text-center"
          style={{
            background: "var(--panel)",
            border: "1px solid rgba(139,144,153,0.12)",
          }}
        >
          <p className="font-mono text-base text-text mb-2">No repos watched yet.</p>
          <p className="font-sans text-sm mb-6" style={{ color: "var(--muted)" }}>
            Connect one to get started.
          </p>
          <Button id="empty-install-btn" variant="primary" size="md">
            Install Telex →
          </Button>
        </div>
      )}
    </div>
  );
}

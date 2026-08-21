import type { Metadata } from "next";
import StatCounter from "@/components/dashboard/StatCounter";
import PatchTicket from "@/components/dashboard/PatchTicket";
import type { PatchSummary } from "@/lib/api";

export const metadata: Metadata = { title: "Dashboard — Overview" };

// Demo data — replace with real API calls once credentials are wired
const DEMO_STATS = {
  repos_watched: 12,
  prs_opened: 128,
  patches_generated: 847,
  merge_rate: 0.94,
};

const DEMO_PATCHES: PatchSummary[] = [
  {
    id: "1",
    package: "openai",
    old_version: "3.2.0",
    new_version: "4.0.0",
    status: "merged",
    pr_url: "#",
    usages_patched: 6,
    opened_at: new Date(Date.now() - 1000 * 60 * 14).toISOString(),
  },
  {
    id: "2",
    package: "axios",
    old_version: "0.27.2",
    new_version: "1.0.0",
    status: "open",
    pr_url: "#",
    usages_patched: 3,
    opened_at: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
  },
  {
    id: "3",
    package: "@prisma/client",
    old_version: "4.16.2",
    new_version: "5.0.0",
    status: "open",
    pr_url: "#",
    usages_patched: 2,
    opened_at: new Date(Date.now() - 1000 * 60 * 60 * 3).toISOString(),
  },
];

export default function DashboardOverview() {
  return (
    <div className="flex flex-col gap-10">
      {/* Header */}
      <div>
        <h1 className="font-mono font-bold text-2xl text-text" style={{ letterSpacing: "-0.02em" }}>
          Overview
        </h1>
        <p className="font-sans text-sm mt-1" style={{ color: "var(--muted)" }}>
          Your dependency health at a glance.
        </p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCounter
          value={DEMO_STATS.repos_watched}
          label="Repos watched"
          color="text"
        />
        <StatCounter
          value={DEMO_STATS.prs_opened}
          label="PRs opened"
          color="patch"
        />
        <StatCounter
          value={DEMO_STATS.patches_generated}
          label="Patches generated"
          color="text"
        />
        <StatCounter
          value={Math.round(DEMO_STATS.merge_rate * 100)}
          label="Merge rate"
          suffix="%"
          color="patch"
        />
      </div>

      {/* Recent patches */}
      <div>
        <h2
          className="font-mono font-semibold text-base text-text mb-4"
          style={{ letterSpacing: "-0.01em" }}
        >
          Recent patches
        </h2>
        <div className="flex flex-col gap-3">
          {DEMO_PATCHES.map((p) => (
            <PatchTicket key={p.id} patch={p} />
          ))}
        </div>
      </div>
    </div>
  );
}

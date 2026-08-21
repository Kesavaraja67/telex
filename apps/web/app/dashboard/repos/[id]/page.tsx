import type { Metadata } from "next";
import DiffViewer from "@/components/dashboard/DiffViewer";
import PatchTicket from "@/components/dashboard/PatchTicket";
import type { PatchSummary } from "@/lib/api";

export const metadata: Metadata = { title: "Repo — Patch History" };

// Demo data
const DEMO_PATCHES: PatchSummary[] = [
  {
    id: "p1",
    package: "openai",
    old_version: "3.2.0",
    new_version: "4.0.0",
    status: "merged",
    pr_url: "https://github.com/acme/api-server/pull/142",
    usages_patched: 6,
    opened_at: new Date(Date.now() - 1000 * 60 * 14).toISOString(),
  },
  {
    id: "p2",
    package: "axios",
    old_version: "0.27.2",
    new_version: "1.0.0",
    status: "open",
    pr_url: "https://github.com/acme/api-server/pull/143",
    usages_patched: 3,
    opened_at: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
  },
];

const DEMO_DIFF = `--- a/src/lib/ai.ts
+++ b/src/lib/ai.ts
@@ -42,7 +42,7 @@ export async function generate(params: GenerateParams) {
   const client = new OpenAI({ apiKey: process.env.OPENAI_KEY });
 
-  const result = await client.createCompletion({
+  const result = await client.completions.create({
     model: params.model,
     prompt: params.prompt,
     max_tokens: params.maxTokens ?? 256,
   });
`;

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function RepoPatchHistoryPage({ params }: PageProps) {
  const { id } = await params;

  return (
    <div className="flex flex-col gap-8">
      <div>
        <div className="font-mono text-xs text-muted mb-1">
          <a href="/dashboard/repos" className="hover:text-text transition-colors">
            ← Repos
          </a>
        </div>
        <h1
          className="font-mono font-bold text-2xl text-text"
          style={{ letterSpacing: "-0.02em" }}
        >
          acme/api-server
        </h1>
        <p className="font-sans text-sm mt-1" style={{ color: "var(--muted)" }}>
          Patch history for this repo.
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Patches list */}
        <div className="flex flex-col gap-3">
          <h2 className="font-mono text-sm font-semibold text-text">Patches</h2>
          {DEMO_PATCHES.map((p) => (
            <PatchTicket key={p.id} patch={p} repoId={id} />
          ))}
        </div>

        {/* Diff viewer */}
        <div className="flex flex-col gap-3">
          <h2 className="font-mono text-sm font-semibold text-text">Latest diff</h2>
          <DiffViewer
            diff={DEMO_DIFF}
            filename="src/lib/ai.ts"
            animated={true}
          />

          {/* Validation report */}
          <div
            className="rounded-lg p-4"
            style={{
              background: "var(--panel)",
              border: "1px solid rgba(139,144,153,0.12)",
            }}
          >
            <div className="font-mono text-xs text-muted mb-3">VALIDATION REPORT</div>
            <div className="flex flex-col gap-2">
              {[
                { label: "Applies cleanly", pass: true },
                { label: "Parses (AST)", pass: true },
                { label: "Typechecks", pass: true },
                { label: "Tests pass", pass: null },
                { label: "Scope OK", pass: true },
              ].map((check) => (
                <div
                  key={check.label}
                  className="flex items-center justify-between"
                >
                  <span className="font-mono text-xs text-muted">
                    {check.label}
                  </span>
                  <span
                    className="font-mono text-xs"
                    style={{
                      color:
                        check.pass === true
                          ? "var(--patch)"
                          : check.pass === false
                          ? "var(--break)"
                          : "var(--muted)",
                    }}
                  >
                    {check.pass === true
                      ? "✓ PASS"
                      : check.pass === false
                      ? "✗ FAIL"
                      : "— N/A"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

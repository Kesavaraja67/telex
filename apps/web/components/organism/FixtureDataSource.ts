import type { IncidentEvent, IncidentGraph, OrganismDataSource } from "./types";

/**
 * Synthetic data source for the marketing HowItWorks section.
 * No backend calls. No customer data. Pure simulation.
 *
 * Plays a realistic 10-node breaking-change scenario in a ~18s loop:
 *  t=0:   change_detected (package upgrade breaks an API)
 *  t=1-5: usage_found x10 (nodes appear one by one)
 *  t=6-8: patch_generated per node (amber pulses)
 *  t=9-12: validating → validation_passed per node (teal pulse, wire steadies)
 *  t=13:  pr_opened (nodes detach to calm resolved ring)
 *  t=15:  reset, loop
 *
 * Brand pillar: "Telex never auto-merges" — the pr_opened event fires but
 * no pr_merged event is ever dispatched from this fixture.
 */

const CHANGE_ID = "fixture-change-001";
const REPO_ID = "fixture-repo-001";

const FILES = [
  { file_path: "src/auth/login.ts", line_start: 42, line_end: 68 },
  { file_path: "src/api/client.ts", line_start: 12, line_end: 35 },
  { file_path: "src/hooks/useSession.ts", line_start: 88, line_end: 110 },
  { file_path: "src/components/Header.tsx", line_start: 24, line_end: 52 },
  { file_path: "src/utils/fetch.ts", line_start: 5, line_end: 44 },
  { file_path: "src/pages/dashboard.tsx", line_start: 133, line_end: 180 },
  { file_path: "src/middleware/auth.ts", line_start: 18, line_end: 49 },
  { file_path: "src/services/analytics.ts", line_start: 60, line_end: 91 },
  { file_path: "tests/auth.spec.ts", line_start: 3, line_end: 38 },
  { file_path: "src/lib/token.ts", line_start: 55, line_end: 72 },
];

const SNAPSHOT: IncidentGraph = {
  detected_change_id: CHANGE_ID,
  repo_id: REPO_ID,
  package: "next-auth",
  symbol_old: "getSession(context)",
  symbol_new: "auth()",
  change_type: "signature_change",
  confidence: 0.96,
  created_at: new Date().toISOString(),
  nodes: FILES.map((f, i) => ({
    code_usage_id: `fixture-usage-${i}`,
    file_path: f.file_path,
    line_start: f.line_start,
    line_end: f.line_end,
    status: "pending",
    patch_verified: null,
    validation: null,
    pr_url: null,
    pr_merged: null,
  })),
};

const TIMELINE_MS: Array<[number, IncidentEvent]> = [
  [
    0,
    {
      event_type: "change_detected",
      detected_change_id: CHANGE_ID,
      repo_id: REPO_ID,
      payload: {
        package: "next-auth",
        symbol_old: "getSession(context)",
        symbol_new: "auth()",
        change_type: "signature_change",
        confidence: 0.96,
      },
    },
  ],
  ...FILES.map(
    (f, i): [number, IncidentEvent] => [
      1200 + i * 380,
      {
        event_type: "usage_found",
        detected_change_id: CHANGE_ID,
        code_usage_id: `fixture-usage-${i}`,
        repo_id: REPO_ID,
        payload: {
          file_path: f.file_path,
          line_start: f.line_start,
          line_end: f.line_end,
        },
      },
    ]
  ),
  ...FILES.map(
    (_, i): [number, IncidentEvent] => [
      5500 + i * 250,
      {
        event_type: "patch_generated",
        code_usage_id: `fixture-usage-${i}`,
        detected_change_id: CHANGE_ID,
        repo_id: REPO_ID,
        payload: { llm_provider: "gemini", llm_model: "gemini-2.0-flash", verified: false },
      },
    ]
  ),
  ...FILES.map(
    (_, i): [number, IncidentEvent] => [
      8500 + i * 350,
      {
        event_type: "validating",
        code_usage_id: `fixture-usage-${i}`,
        detected_change_id: CHANGE_ID,
        repo_id: REPO_ID,
        payload: {},
      },
    ]
  ),
  ...FILES.map(
    (_, i): [number, IncidentEvent] => [
      11000 + i * 350,
      {
        event_type: "validation_passed",
        code_usage_id: `fixture-usage-${i}`,
        detected_change_id: CHANGE_ID,
        repo_id: REPO_ID,
        payload: {
          applies_cleanly: true,
          typechecks: true,
          tests_pass: true,
          scope_ok: true,
          verification_mode: "github_actions",
        },
      },
    ]
  ),
  [
    14500,
    {
      event_type: "pr_opened",
      repo_id: REPO_ID,
      detected_change_id: CHANGE_ID,
      payload: {
        github_pr_url: "https://github.com/org/repo/pull/42",
        github_pr_number: 42,
      },
    },
  ],
  // NOTE: no pr_merged — Telex never auto-merges.
];

const LOOP_MS = 18000;

export class FixtureDataSource implements OrganismDataSource {
  async fetchSnapshot(): Promise<IncidentGraph> {
    return structuredClone(SNAPSHOT);
  }

  subscribe(onEvent: (e: IncidentEvent) => void): () => void {
    const timers: ReturnType<typeof setTimeout>[] = [];
    let loopTimer: ReturnType<typeof setTimeout>;

    const startLoop = () => {
      for (const [delay, event] of TIMELINE_MS) {
        timers.push(setTimeout(() => onEvent(event), delay));
      }
      loopTimer = setTimeout(() => {
        timers.length = 0;
        startLoop();
      }, LOOP_MS);
    };

    startLoop();

    return () => {
      timers.forEach(clearTimeout);
      clearTimeout(loopTimer);
    };
  }
}

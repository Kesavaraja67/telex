"use client";

import { useState, useEffect } from "react";
import StatCounter from "@/components/dashboard/StatCounter";
import RecoveryTicket from "@/components/dashboard/RecoveryTicket";
import type { RecoveryEvent, RecoveryStats } from "@/lib/api";

// ── Demo data ─────────────────────────────────────────────────────────────────
// Realistic demo: NOT 100% recovery (that would be dishonest).
// Tier1/Tier2 split reflects real distribution: most failures are deterministic.
const DEMO_STATS: RecoveryStats = {
  total_payment_attempts: 247,
  total_recovery_events: 63,
  recovered: 41,
  escalated: 9,
  unresolved: 13,
  recovery_rate: 0.794,
  tier1_classified: 51,   // 81% deterministic — no LLM needed
  tier2_classified: 12,   // 19% genuinely ambiguous — LLM called
};

const DEMO_EVENTS: RecoveryEvent[] = [
  {
    id: "1",
    payment_attempt_id: "pa-1",
    failure_type: "timeout",
    classification: "transient",
    action_taken: "Classified via deterministic rule (no LLM call — failure type has a known, unambiguous cause): timeout → transient",
    llm_provider: "none",
    llm_model: "none",
    outcome: "recovered",
    pull_request_id: null,
    detected_at: new Date(Date.now() - 1000 * 60 * 3).toISOString(),
    resolved_at: new Date(Date.now() - 1000 * 60 * 2).toISOString(),
  },
  {
    id: "2",
    payment_attempt_id: "pa-2",
    failure_type: "webhook_signature_mismatch",
    classification: "code_defect",
    action_taken: "Classified via deterministic rule (no LLM call — failure type has a known, unambiguous cause): webhook_signature_mismatch → code_defect",
    llm_provider: "none",
    llm_model: "none",
    outcome: "escalated",
    pull_request_id: null,
    detected_at: new Date(Date.now() - 1000 * 60 * 18).toISOString(),
    resolved_at: new Date(Date.now() - 1000 * 60 * 16).toISOString(),
  },
  {
    id: "3",
    payment_attempt_id: "pa-3",
    failure_type: "card_declined",
    classification: "transient",
    action_taken: "Classified via LLM: Card decline at the payment rail level is typically a customer-side condition, not a code defect in our integration.",
    llm_provider: "gemini",
    llm_model: "gemini-2.0-flash",
    outcome: "unresolved",
    pull_request_id: null,
    detected_at: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
    resolved_at: null,
  },
  {
    id: "4",
    payment_attempt_id: "pa-4",
    failure_type: "db_unavailable",
    classification: "transient",
    action_taken: "Classified via deterministic rule (no LLM call — failure type has a known, unambiguous cause): db_unavailable → transient",
    llm_provider: "none",
    llm_model: "none",
    outcome: "recovered",
    pull_request_id: null,
    detected_at: new Date(Date.now() - 1000 * 60 * 70).toISOString(),
    resolved_at: new Date(Date.now() - 1000 * 60 * 68).toISOString(),
  },
  {
    id: "5",
    payment_attempt_id: "pa-5",
    failure_type: "payment_malformed_response",
    classification: "code_defect",
    action_taken: "Classified via LLM: The malformed response structure indicates a schema mismatch in our response parsing code, not a transient network condition.",
    llm_provider: "gemini",
    llm_model: "gemini-2.0-flash",
    outcome: "escalated",
    pull_request_id: null,
    detected_at: new Date(Date.now() - 1000 * 60 * 120).toISOString(),
    resolved_at: new Date(Date.now() - 1000 * 60 * 118).toISOString(),
  },
];

// ── Component ─────────────────────────────────────────────────────────────────

export default function RecoveryPage() {
  const [stats, setStats] = useState<RecoveryStats>(DEMO_STATS);
  const [events, setEvents] = useState<RecoveryEvent[]>(DEMO_EVENTS);
  const [count, setCount] = useState(10);
  const [failureRate, setFailureRate] = useState(0.3);
  const [isRunning, setIsRunning] = useState(false);
  const [runResult, setRunResult] = useState<string | null>(null);

  async function loadData() {
    try {
      const { getRecoveryStats, getRecoveryEvents } = await import("@/lib/api");
      const [fetchedStats, fetchedEvents] = await Promise.all([
        getRecoveryStats(),
        getRecoveryEvents(50, 0),
      ]);
      if (fetchedStats && fetchedStats.total_recovery_events > 0) {
        setStats(fetchedStats);
      }
      if (fetchedEvents && fetchedEvents.length > 0) {
        setEvents(fetchedEvents);
      }
    } catch {
      // Backend not reachable or error — keep demo state
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  async function handleBatchRun() {
    setIsRunning(true);
    setRunResult(null);
    try {
      const { triggerBatchRun } = await import("@/lib/api");
      const result = await triggerBatchRun({
        count,
        failure_rate: failureRate,
        client_request_id: `demo-${Date.now()}`,
      });
      setRunResult(
        result.status === "existing"
          ? `Returned existing batch (${result.payment_attempt_ids.length} attempts)`
          : `Created ${result.payment_attempt_ids.length} attempts — worker processing...`
      );
      // Refresh after short delay for worker processing
      setTimeout(loadData, 1500);
    } catch {
      setRunResult("API not reachable — showing demo data");
    } finally {
      setIsRunning(false);
    }
  }

  const totalClassified = stats.tier1_classified + stats.tier2_classified;
  const tier1Pct = totalClassified > 0
    ? Math.round((stats.tier1_classified / totalClassified) * 100)
    : 0;

  return (
    <div className="flex flex-col gap-10">
      {/* Header */}
      <div>
        <h1
          className="font-mono font-bold text-2xl text-text"
          style={{ letterSpacing: "-0.02em" }}
        >
          Payment Recovery
        </h1>
        <p className="font-sans text-sm mt-1" style={{ color: "var(--muted)" }}>
          Engine B — runtime failure detection, two-tier classification, and auto-retry.
        </p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCounter
          value={Math.round(stats.recovery_rate * 100)}
          label="Recovery rate"
          suffix="%"
          color="patch"
        />
        <StatCounter
          value={stats.recovered}
          label="Auto-recovered"
          color="text"
        />
        <StatCounter
          value={stats.escalated}
          label="Escalated to PR"
          color="patch"
        />
        <StatCounter
          value={tier1Pct}
          label="Tier 1 (no LLM) %"
          suffix="%"
          color="text"
        />
      </div>

      {/* Classifier breakdown */}
      <div className="glass-surface p-5 bg-black/60 backdrop-blur-xl">
        <h2
          className="font-mono font-semibold text-base text-text mb-4"
          style={{ letterSpacing: "-0.01em" }}
        >
          Two-tier classifier breakdown
        </h2>
        <div className="flex items-center gap-4">
          <div className="flex-1 h-2 rounded-full bg-white/10 overflow-hidden">
            <div
              className="h-full rounded-full bg-[#4FD1C5] transition-all"
              style={{ width: `${tier1Pct}%` }}
            />
          </div>
          <span className="font-mono text-xs text-[#8B9099] flex-shrink-0">
            <span className="text-[#4FD1C5]">{stats.tier1_classified}</span> RULE
            &nbsp;/&nbsp;
            <span className="text-[#A78BFA]">{stats.tier2_classified}</span> LLM
          </span>
        </div>
        <p className="font-sans text-xs text-[#7A7F87] mt-2">
          {tier1Pct}% of failures classified deterministically (timeout, db_unavailable, webhook mismatch) — no LLM call needed.
          Only genuinely ambiguous cases use the LLM.
        </p>
      </div>

      {/* Batch-run control */}
      <div className="glass-surface p-5 bg-black/60 backdrop-blur-xl">
        <h2
          className="font-mono font-semibold text-base text-text mb-4"
          style={{ letterSpacing: "-0.01em" }}
        >
          Trigger batch run
        </h2>
        <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-end">
          <div className="flex flex-col gap-1.5">
            <label className="font-mono text-xs text-[#7A7F87]">Attempts</label>
            <input
              id="batch-run-count"
              type="number"
              min={1}
              max={100}
              value={count}
              onChange={(e) => setCount(Math.max(1, Math.min(100, Number(e.target.value))))}
              className="font-mono text-sm bg-black/50 border border-white/10 rounded-lg px-3 py-2 text-white w-28 focus:outline-none focus:border-white/30"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="font-mono text-xs text-[#7A7F87]">
              Failure rate ({Math.round(failureRate * 100)}%)
            </label>
            <input
              id="batch-run-failure-rate"
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={failureRate}
              onChange={(e) => setFailureRate(Number(e.target.value))}
              className="w-40 accent-[#4FD1C5]"
            />
          </div>
          <button
            id="batch-run-submit"
            onClick={handleBatchRun}
            disabled={isRunning}
            className="font-mono text-xs px-4 py-2 rounded-lg border border-white/20 text-white hover:bg-white/[0.06] disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {isRunning ? "Running…" : "Run batch →"}
          </button>
        </div>
        {runResult && (
          <p className="font-mono text-xs text-[#4FD1C5] mt-3">{runResult}</p>
        )}
      </div>

      {/* Recent recovery events */}
      <div>
        <h2
          className="font-mono font-semibold text-base text-text mb-4"
          style={{ letterSpacing: "-0.01em" }}
        >
          Recent recovery events
        </h2>
        <div className="flex flex-col gap-3">
          {events.map((e) => (
            <RecoveryTicket key={e.id} event={e} />
          ))}
        </div>
      </div>
    </div>
  );
}

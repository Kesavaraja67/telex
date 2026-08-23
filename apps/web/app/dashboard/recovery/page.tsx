"use client";

import { useState, useEffect, useRef } from "react";
import { animate } from "animejs";
import { AnimatePresence, motion } from "motion/react";
import StatCounter from "@/components/dashboard/StatCounter";
import RecoveryTicket from "@/components/dashboard/RecoveryTicket";
import RecoveryPipelineVisualizer from "@/components/dashboard/RecoveryPipelineVisualizer";
import BorderBeam from "@/components/ui/BorderBeam";
import SpotlightCard from "@/components/ui/SpotlightCard";
import KineticHeader from "@/components/ui/KineticHeader";
import CyberGridBackground from "@/components/ui/CyberGridBackground";
import TickerRibbon from "@/components/ui/TickerRibbon";
import type { RecoveryEvent, RecoveryStats } from "@/lib/api";

// ── Demo fallback data (Pure Monochrome) ──────────────────────────────────────
const DEMO_STATS: RecoveryStats = {
  total_payment_attempts: 247,
  total_recovery_events: 63,
  recovered: 41,
  escalated: 9,
  unresolved: 13,
  recovery_rate: 0.794,
  tier1_classified: 51,
  tier2_classified: 12,
  revenue_at_risk: 18450000,    // ₹1,84,500 in paise
  revenue_recovered: 14650000,  // ₹1,46,500 in paise
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
    amount: 50000,
    detected_at: "2026-08-22T13:40:00.000Z",
    resolved_at: "2026-08-22T13:41:00.000Z",
  },
  {
    id: "2",
    payment_attempt_id: "pa-2",
    failure_type: "card_declined",
    classification: "transient",
    action_taken: "Stopped retrying after 2 attempts — repeated card decline is unlikely to resolve automatically. Recommend alternate payment method.",
    llm_provider: "none",
    llm_model: "none",
    outcome: "unresolved",
    pull_request_id: null,
    amount: 120000,
    detected_at: "2026-08-22T13:35:00.000Z",
    resolved_at: "2026-08-22T13:36:00.000Z",
  },
  {
    id: "3",
    payment_attempt_id: "pa-3",
    failure_type: "webhook_signature_mismatch",
    classification: "code_defect",
    action_taken: "Classified via deterministic rule (no LLM call — failure type has a known, unambiguous cause): webhook_signature_mismatch → code_defect",
    llm_provider: "none",
    llm_model: "none",
    outcome: "escalated",
    pull_request_id: null,
    amount: 75000,
    detected_at: "2026-08-22T13:20:00.000Z",
    resolved_at: "2026-08-22T13:22:00.000Z",
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
    amount: 30000,
    detected_at: "2026-08-22T12:30:00.000Z",
    resolved_at: "2026-08-22T12:32:00.000Z",
  },
];

const inrFormatter = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

export default function RecoveryPage() {
  const [stats, setStats] = useState<RecoveryStats>(DEMO_STATS);
  const [events, setEvents] = useState<RecoveryEvent[]>(DEMO_EVENTS);
  const [count, setCount] = useState(10);
  const [failureRate, setFailureRate] = useState(0.3);
  const [isRunning, setIsRunning] = useState(false);
  const [runResult, setRunResult] = useState<string | null>(null);

  // Animation refs
  const revenueDisplayRef = useRef<HTMLSpanElement>(null);
  const atRiskDisplayRef = useRef<HTMLSpanElement>(null);
  const rippleRef = useRef<SVGCircleElement>(null);
  const streamCanvasRef = useRef<HTMLCanvasElement>(null);

  const prevRecoveredRef = useRef<number>(stats.revenue_recovered);
  const prevAtRiskRef = useRef<number>(stats.revenue_at_risk);
  const isInitialMount = useRef<boolean>(true);

  // 1. Ambient Leak Particles on "Revenue at Risk" card (continuous, subtle, slow upward drift)
  useEffect(() => {
    const canvas = streamCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    const particles: { x: number; y: number; speed: number; opacity: number; size: number }[] = [];
    for (let i = 0; i < 18; i++) {
      particles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        speed: 0.2 + Math.random() * 0.3,
        opacity: 0.15 + Math.random() * 0.2,
        size: 1.2 + Math.random() * 1.5,
      });
    }

    const render = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = "#FFFFFF";

      for (const p of particles) {
        p.y -= p.speed;
        if (p.y < 0) {
          p.y = canvas.height;
          p.x = Math.random() * canvas.width;
        }
        ctx.globalAlpha = p.opacity * (p.y / canvas.height);
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fill();
      }
      animId = requestAnimationFrame(render);
    };
    render();

    return () => cancelAnimationFrame(animId);
  }, []);

  // 2. Dual Synchronized Number Tweening & Capture Ripple Confirmation
  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }

    const startRecoveredRupees = Math.round(prevRecoveredRef.current / 100);
    const targetRecoveredRupees = Math.round(stats.revenue_recovered / 100);
    const startAtRiskRupees = Math.round(prevAtRiskRef.current / 100);
    const targetAtRiskRupees = Math.round(stats.revenue_at_risk / 100);

    const hasRecoveredIncreased = targetRecoveredRupees > startRecoveredRupees;

    prevRecoveredRef.current = stats.revenue_recovered;
    prevAtRiskRef.current = stats.revenue_at_risk;

    // Tween Recovered Number
    if (revenueDisplayRef.current) {
      const recObj = { val: startRecoveredRupees };
      animate(recObj, {
        val: targetRecoveredRupees,
        ease: "outExpo",
        duration: 1000,
        onUpdate: () => {
          if (revenueDisplayRef.current) {
            revenueDisplayRef.current.textContent = inrFormatter.format(Math.round(recObj.val));
          }
        },
      });
    }

    // Tween At-Risk Number in lockstep
    if (atRiskDisplayRef.current) {
      const riskObj = { val: startAtRiskRupees };
      animate(riskObj, {
        val: targetAtRiskRupees,
        ease: "outExpo",
        duration: 1000,
        onUpdate: () => {
          if (atRiskDisplayRef.current) {
            atRiskDisplayRef.current.textContent = inrFormatter.format(Math.round(riskObj.val));
          }
        },
      });
    }

    // Trigger subtle ripple ring on the recovered card when money lands
    if (hasRecoveredIncreased && rippleRef.current) {
      const rObj = { r: 10, opacity: 0.9 };
      animate(rObj, {
        r: 50,
        opacity: 0,
        ease: "outExpo",
        duration: 900,
        onUpdate: () => {
          if (rippleRef.current) {
            rippleRef.current.setAttribute("r", String(rObj.r));
            rippleRef.current.setAttribute("stroke-opacity", String(rObj.opacity));
          }
        },
      });
    }
  }, [stats.revenue_recovered, stats.revenue_at_risk]);

  const isFetchingRef = useRef(false);
  const isMountedRef = useRef(true);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  async function loadData() {
    if (isFetchingRef.current || !isMountedRef.current) return;
    isFetchingRef.current = true;
    try {
      const { getRecoveryStats, getRecoveryEvents } = await import("@/lib/api");
      const [fetchedStats, fetchedEvents] = await Promise.all([
        getRecoveryStats(),
        getRecoveryEvents(50, 0),
      ]);
      if (!isMountedRef.current) return;
      if (fetchedStats && fetchedStats.total_recovery_events > 0) {
        setStats(fetchedStats);
      }
      if (fetchedEvents && fetchedEvents.length > 0) {
        setEvents(fetchedEvents);
      }
    } catch {
      // Backend not reachable — keep current state
    } finally {
      isFetchingRef.current = false;
    }
  }

  useEffect(() => {
    isMountedRef.current = true;
    loadData();
    // 2.5-second background polling for live updates
    const interval = setInterval(loadData, 2500);
    return () => {
      isMountedRef.current = false;
      clearInterval(interval);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
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
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(loadData, 1200);
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
    <div className="flex flex-col gap-8 relative z-10">
      {/* Pure White Cybernetic Background Ambient Grid & Light Mesh */}
      <CyberGridBackground />

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] tracking-wider text-[#A1A1AA] uppercase font-semibold">
              Engine B · Runtime Recovery
            </span>
            <span className="text-[#3F3F46]">/</span>
            <span className="font-mono text-[10px] text-white">Payment Pipeline</span>
          </div>
          <h1 className="font-mono font-bold text-xl sm:text-2xl text-white tracking-tight">
            Payment Recovery & Telemetry
          </h1>
          <p className="font-sans text-xs text-[#71717A]">
            Zero-token deterministic classification, auto-retry backoff, and self-healing escalations.
          </p>
        </div>

        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/[0.04] border border-white/10 self-start sm:self-center">
          <span className="relative flex h-1.5 w-1.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-white opacity-75" />
            <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-white shadow-[0_0_6px_#FFFFFF]" />
          </span>
          <span className="font-mono text-[11px] text-white font-medium">
            Telemetry Live
          </span>
        </div>
      </div>

      {/* Top-Line Real ₹ Revenue Math Cards (Pure Monochrome High-Contrast Glass) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 relative">
        {/* Total Revenue Recovered Card with White Laser BorderBeam */}
        <SpotlightCard
          spotlightColor="rgba(255, 255, 255, 0.12)"
          className="p-6 bg-black/80 backdrop-blur-2xl border border-white/10 flex flex-col justify-between relative shadow-2xl"
        >
          {/* Pure White Traveling Perimeter Laser */}
          <BorderBeam size={280} duration={10} colorFrom="#FFFFFF" colorTo="rgba(255, 255, 255, 0.15)" borderWidth={1.5} />

          {/* Pure White Ripple Ping SVG on impact */}
          <svg className="absolute top-8 left-36 w-32 h-32 pointer-events-none -translate-x-1/2 -translate-y-1/2 overflow-visible">
            <circle
              ref={rippleRef}
              cx="64"
              cy="64"
              r="0"
              fill="none"
              stroke="#FFFFFF"
              strokeWidth="2"
              strokeOpacity="0"
            />
          </svg>

          <div className="relative z-10">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs text-[#A1A1AA] uppercase tracking-wider">
                Total Revenue Recovered
              </span>
              <span className="font-mono text-[10px] text-white font-bold px-2.5 py-0.5 rounded-full bg-white/10 border border-white/20">
                AUTO-RESTORED
              </span>
            </div>
            <div className="mt-3 flex items-baseline gap-3">
              <span
                ref={revenueDisplayRef}
                className="font-mono font-bold text-3xl md:text-5xl text-white tracking-tight drop-shadow-[0_0_24px_rgba(255,255,255,0.4)]"
              >
                {inrFormatter.format(stats.revenue_recovered / 100)}
              </span>
            </div>
          </div>
          <p className="font-sans text-xs text-[#71717A] mt-4 relative z-10">
            Real sum of {stats.recovered} auto-recovered payment transactions.
          </p>
        </SpotlightCard>

        {/* Revenue at Risk Card with Ambient Leak Particle Stream */}
        <SpotlightCard
          spotlightColor="rgba(255, 255, 255, 0.08)"
          className="p-6 bg-black/80 backdrop-blur-2xl border border-white/10 flex flex-col justify-between relative shadow-2xl"
        >
          {/* Ambient Leak Canvas */}
          <canvas
            ref={streamCanvasRef}
            width={320}
            height={140}
            className="absolute inset-0 w-full h-full pointer-events-none opacity-40"
          />

          <div className="relative z-10">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs text-[#A1A1AA] uppercase tracking-wider">
                Revenue at Risk
              </span>
              <span className="font-mono text-[10px] text-[#A1A1AA] px-2.5 py-0.5 rounded-full bg-white/5 border border-white/15">
                ACTIVE / INTERCEPTED
              </span>
            </div>
            <div className="mt-3 flex items-baseline gap-3">
              <span
                ref={atRiskDisplayRef}
                className="font-mono font-bold text-3xl md:text-5xl text-white tracking-tight"
              >
                {inrFormatter.format(stats.revenue_at_risk / 100)}
              </span>
            </div>
          </div>
          <p className="font-sans text-xs text-[#71717A] mt-4 relative z-10">
            Total volume across {stats.total_recovery_events} intercepted failure events.
          </p>
        </SpotlightCard>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <SpotlightCard className="p-1">
          <StatCounter
            value={Math.round(stats.recovery_rate * 100)}
            label="Recovery rate"
            suffix="%"
          />
        </SpotlightCard>
        <SpotlightCard className="p-1">
          <StatCounter
            value={stats.recovered}
            label="Auto-recovered"
          />
        </SpotlightCard>
        <SpotlightCard className="p-1">
          <StatCounter
            value={stats.escalated}
            label="Escalated to PR"
          />
        </SpotlightCard>
        <SpotlightCard className="p-1">
          <StatCounter
            value={tier1Pct}
            label="Tier 1 (no LLM) %"
            suffix="%"
          />
        </SpotlightCard>
      </div>

      {/* Classifier breakdown */}
      <SpotlightCard className="p-6 bg-black/70 backdrop-blur-xl">
        <h2
          className="font-mono font-semibold text-base text-white mb-4 tracking-tight flex items-center gap-2.5"
        >
          <span>Two-tier classifier breakdown</span>
          <span className="text-[10px] font-mono text-white px-2 py-0.5 rounded bg-white/10 border border-white/20">
            0-Token Rule Priority
          </span>
        </h2>
        <div className="flex items-center gap-4">
          <div className="flex-1 h-2 rounded-full bg-white/10 overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${tier1Pct}%` }}
              transition={{ duration: 1, ease: "easeOut" }}
              className="h-full rounded-full bg-white shadow-[0_0_12px_#FFFFFF]"
            />
          </div>
          <span className="font-mono text-xs text-[#A1A1AA] flex-shrink-0">
            <span className="text-white font-bold">{stats.tier1_classified}</span> RULE
            &nbsp;/&nbsp;
            <span className="text-white font-medium">{stats.tier2_classified}</span> LLM
          </span>
        </div>
        <p className="font-sans text-xs text-[#71717A] mt-3">
          {tier1Pct}% of failures classified deterministically (timeout, db_unavailable, webhook mismatch) — no LLM call needed.
          Only genuinely ambiguous cases use the LLM.
        </p>
      </SpotlightCard>

      {/* Real Live Pipeline Visualizer */}
      <RecoveryPipelineVisualizer events={events} isRunning={isRunning} />

      {/* Batch-run control */}
      <SpotlightCard className="p-6 bg-black/70 backdrop-blur-xl relative overflow-hidden">
        {/* Pure White Terminal Scanline sweep */}
        <div className="animate-terminal-scan" />

        <h2
          className="font-mono font-semibold text-base text-white mb-4 tracking-tight flex items-center gap-2"
        >
          <span>Trigger Real-time Batch Run</span>
          <span className="font-mono text-[10px] text-[#71717A] font-normal">
            (Simulate High-Concurrency Traffic)
          </span>
        </h2>
        <div className="flex flex-col sm:flex-row gap-5 items-start sm:items-end">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="batch-run-count" className="font-mono text-xs text-[#71717A]">Attempts</label>
            <input
              id="batch-run-count"
              type="number"
              min={1}
              max={100}
              value={count}
              onChange={(e) => setCount(Math.max(1, Math.min(100, Number(e.target.value))))}
              className="font-mono text-sm bg-black/70 border border-white/20 rounded-lg px-3 py-2 text-white w-32 focus:outline-none focus:border-white transition-colors"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="batch-run-failure-rate" className="font-mono text-xs text-[#71717A]">
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
              className="w-44 accent-white cursor-pointer"
            />
          </div>
          <motion.button
            id="batch-run-submit"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={handleBatchRun}
            disabled={isRunning}
            className="font-mono text-xs font-semibold px-5 py-2.5 rounded-lg border border-white bg-white text-black hover:bg-white/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-[0_0_20px_rgba(255,255,255,0.2)]"
          >
            {isRunning ? "Executing Pipeline…" : "Run Batch Simulation →"}
          </motion.button>
        </div>
        {runResult && (
          <motion.p
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            className="font-mono text-xs text-white mt-3 font-medium"
          >
            {runResult}
          </motion.p>
        )}
      </SpotlightCard>

      {/* Recent recovery events */}
      <div className="flex flex-col gap-3">
        <h2
          className="font-mono font-semibold text-base text-white tracking-tight flex items-center justify-between"
        >
          <span>Recent Recovery Events</span>
          <span className="font-mono text-xs text-[#71717A] font-normal">
            Real-time Feed ({events.length})
          </span>
        </h2>
        <div className="flex flex-col gap-3">
          <AnimatePresence mode="popLayout">
            {events.map((e) => (
              <RecoveryTicket key={e.id} event={e} />
            ))}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}

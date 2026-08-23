"use client";

import React, { useMemo } from "react";
import { motion } from "motion/react";
import BorderBeam from "@/components/ui/BorderBeam";
import SpotlightCard from "@/components/ui/SpotlightCard";
import type { RecoveryEvent } from "@/lib/api";

interface RecoveryPipelineVisualizerProps {
  events: RecoveryEvent[];
  isRunning?: boolean;
}

export default function RecoveryPipelineVisualizer({ events, isRunning = false }: RecoveryPipelineVisualizerProps) {
  // Find the latest active/resolved event from real polled data
  const latestEvent = events[0] || null;

  // Derive active pipeline stage from the latest real event
  const stageInfo = useMemo(() => {
    if (!latestEvent) {
      return {
        step: 0,
        status: "idle",
        node4Label: "[IDLE]",
        text: "Pipeline standby — waiting for incoming transactions",
      };
    }

    if (latestEvent.outcome === "recovered") {
      return {
        step: 4,
        status: "recovered",
        node4Label: "[RESOLVED]",
        isRule: latestEvent.llm_provider === "none",
        text: `Auto-Recovered: ${latestEvent.failure_type} resolved via backoff retry`,
      };
    }

    if (latestEvent.outcome === "escalated") {
      return {
        step: 4,
        status: "escalated",
        node4Label: "[PR OPENED]",
        isRule: latestEvent.llm_provider === "none",
        text: `Escalated: ${latestEvent.failure_type} verified & opened on GitHub`,
      };
    }

    if (latestEvent.action_taken.startsWith("Stopped retrying")) {
      return {
        step: 4,
        status: "stopped",
        node4Label: "[STOPPED 2/2]",
        isRule: latestEvent.llm_provider === "none",
        text: `Deliberate Stop: repeated ${latestEvent.failure_type} halted`,
      };
    }

    return {
      step: 2,
      status: "processing",
      node4Label: "[ANALYZING]",
      isRule: latestEvent.llm_provider === "none",
      text: `Processing: ${latestEvent.failure_type} detected`,
    };
  }, [latestEvent]);

  const activeStep = isRunning ? 2 : stageInfo.step;

  return (
    <SpotlightCard
      spotlightColor="rgba(255, 255, 255, 0.08)"
      enableTilt={false}
      className="p-6 bg-black/80 backdrop-blur-2xl border border-white/10 relative overflow-hidden flex flex-col gap-6"
    >
      {/* Pure White Laser BorderBeam */}
      <BorderBeam size={320} duration={12} colorFrom="#FFFFFF" colorTo="rgba(255, 255, 255, 0.15)" delay={4} />

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.08] pb-4 relative z-10">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-white opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-white shadow-[0_0_8px_#FFFFFF]" />
            </span>
            <h2 className="font-mono font-bold text-lg text-white tracking-tight">
              Live Pipeline & Two-Tier Classifier
            </h2>
            <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-white/10 text-white border border-white/20">
              {isRunning ? "Active Batch" : (events.length > 0 ? "Synced" : "Standby")}
            </span>
          </div>
          <p className="font-sans text-xs text-[#A1A1AA] mt-1">
            Deterministic rule-table routing with autonomous LLM fallback and real verification gate.
          </p>
        </div>

        <div className="font-mono text-xs text-[#A1A1AA]">
          Events Intercepted: <span className="text-white font-semibold">{events.length}</span>
        </div>
      </div>

      {/* Node Flow Diagram */}
      <div className="p-6 rounded-xl bg-black/60 border border-white/[0.06] relative overflow-hidden">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 relative z-10">
          {/* Node 1: Ingestion */}
          <motion.div
            animate={{
              borderColor: activeStep >= 1 ? "rgba(255,255,255,0.4)" : "rgba(255,255,255,0.06)",
              backgroundColor: activeStep >= 1 ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.02)",
              opacity: activeStep === 0 ? 0.6 : 1,
            }}
            transition={{ duration: 0.3 }}
            className="p-4 rounded-xl border flex flex-col gap-2 relative shadow-lg"
          >
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase text-[#A1A1AA] tracking-wider">Node 01</span>
              {activeStep >= 1 && (
                <span className="h-1.5 w-1.5 rounded-full bg-white shadow-[0_0_8px_#FFFFFF]" />
              )}
            </div>
            <h3 className="font-mono text-sm font-semibold text-white">Payment Gate</h3>
            <p className="font-sans text-xs text-[#A1A1AA]">
              {latestEvent ? `Failure: ${latestEvent.failure_type}` : "Razorpay payment failure ingestion"}
            </p>
            <div className="mt-auto pt-2 border-t border-white/[0.06] font-mono text-[10px] text-white">
              {latestEvent ? latestEvent.payment_attempt_id.slice(0, 12) : "STANDBY"}
            </div>
          </motion.div>

          {/* Node 2: Detector */}
          <motion.div
            animate={{
              borderColor: activeStep >= 2 ? "rgba(255,255,255,0.4)" : "rgba(255,255,255,0.06)",
              backgroundColor: activeStep >= 2 ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.02)",
              opacity: activeStep < 2 ? 0.5 : 1,
            }}
            transition={{ duration: 0.3 }}
            className="p-4 rounded-xl border flex flex-col gap-2 relative shadow-lg"
          >
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase text-[#A1A1AA] tracking-wider">Node 02</span>
              {activeStep >= 2 && (
                <span className="h-1.5 w-1.5 rounded-full bg-white shadow-[0_0_8px_#FFFFFF]" />
              )}
            </div>
            <h3 className="font-mono text-sm font-semibold text-white">Failure Detector</h3>
            <p className="font-sans text-xs text-[#A1A1AA]">
              Atomic RecoveryEvent generated with attempt tracking.
            </p>
            <div className="mt-auto pt-2 border-t border-white/[0.06] font-mono text-[10px] text-white">
              detect_payment_failure
            </div>
          </motion.div>

          {/* Node 3: Brain */}
          <motion.div
            animate={{
              borderColor: activeStep >= 3 ? "rgba(255,255,255,0.4)" : "rgba(255,255,255,0.06)",
              backgroundColor: activeStep >= 3 ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.02)",
              opacity: activeStep < 3 ? 0.5 : 1,
            }}
            transition={{ duration: 0.3 }}
            className="p-4 rounded-xl border flex flex-col gap-2 relative shadow-lg"
          >
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase text-[#A1A1AA] tracking-wider">Node 03</span>
              {activeStep >= 3 && (
                <span className="h-1.5 w-1.5 rounded-full bg-white shadow-[0_0_8px_#FFFFFF]" />
              )}
            </div>
            <h3 className="font-mono text-sm font-semibold text-white">Two-Tier Brain</h3>
            <p className="font-sans text-xs text-[#A1A1AA]">
              {latestEvent && latestEvent.llm_provider !== "none"
                ? `Tier 2 LLM: ${latestEvent.llm_model}`
                : "Tier 1: Deterministic rule table (<1ms)"}
            </p>
            <div className="mt-auto pt-2 border-t border-white/[0.06] font-mono text-[10px] text-white">
              {latestEvent && latestEvent.llm_provider !== "none" ? "Tier 2 (LLM)" : "Tier 1 (Rule Table)"}
            </div>
          </motion.div>

          {/* Node 4: Resolution */}
          <motion.div
            animate={{
              borderColor: activeStep >= 4 ? "rgba(255,255,255,0.5)" : "rgba(255,255,255,0.06)",
              backgroundColor: activeStep >= 4 ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.02)",
              opacity: activeStep < 4 ? 0.5 : 1,
            }}
            transition={{ duration: 0.3 }}
            className="p-4 rounded-xl border flex flex-col gap-2 relative shadow-lg"
          >
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-wider text-[#A1A1AA]">
                Node 04
              </span>
              {activeStep >= 4 && (
                <span className="h-1.5 w-1.5 rounded-full bg-white shadow-[0_0_8px_#FFFFFF]" />
              )}
            </div>
            <h3 className="font-mono text-sm font-semibold text-white">Resolution Engine</h3>
            <p className="font-sans text-xs text-[#A1A1AA]">
              {stageInfo.text}
            </p>
            <div className="mt-auto pt-2 border-t border-white/[0.06] font-mono text-[10px] font-semibold text-white">
              {stageInfo.node4Label}
            </div>
          </motion.div>
        </div>
      </div>

      {/* Real-time Telemetry Stream */}
      <div className="rounded-xl bg-[#080808] border border-white/10 p-4 font-mono text-xs relative overflow-hidden">
        <div className="animate-terminal-scan" />

        <div className="flex items-center justify-between pb-2 mb-3 border-b border-white/[0.06] text-[#71717A] relative z-10">
          <div className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-white" />
            <span className="text-[11px] text-[#A1A1AA] font-medium tracking-wide">SYSTEM TELEMETRY STREAM</span>
          </div>
          <span className="text-[10px] text-white">
            {latestEvent ? `EVENT: ${latestEvent.id.slice(0, 8)}` : "STANDBY"}
          </span>
        </div>

        <div className="flex flex-col gap-2 min-h-[60px] relative z-10">
          {events.length === 0 ? (
            <div className="text-[#71717A] italic py-3 text-center">
              No recent events. Trigger a batch run or test transaction to observe real-time recovery.
            </div>
          ) : (
            events.slice(0, 3).map((e) => (
              <div key={e.id} className="flex items-start gap-3">
                <span suppressHydrationWarning className="text-[#71717A] flex-shrink-0">
                  {new Date(e.detected_at).toLocaleTimeString()}
                </span>
                <span
                  className="px-1.5 py-0.2 rounded text-[10px] font-semibold flex-shrink-0 bg-white/10 text-white border border-white/15"
                >
                  [{e.llm_provider !== "none" ? "TIER 2 LLM" : "TIER 1 RULE"}]
                </span>
                <span className="text-white/90 leading-relaxed truncate">
                  {e.action_taken}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </SpotlightCard>
  );
}

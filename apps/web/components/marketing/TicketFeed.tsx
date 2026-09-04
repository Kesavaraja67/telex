"use client";

import { useEffect, useRef, useState } from "react";
import { animateTicketIn, animateDiffReveal, prefersReducedMotion } from "@/lib/animations";
import Badge from "@/components/ui/Badge";

export interface TicketData {
  id: string;
  package: string;
  oldVersion: string;
  newVersion: string;
  diff: string;
  timestamp: string;
  status: "open" | "merged" | "closed";
  usagesPatched: number;
}

const DEMO_TICKETS: TicketData[] = [
  {
    id: "1",
    package: "razorpay / checkout",
    oldVersion: "order_total_mismatch",
    newVersion: "ci-verified",
    diff: "-const order = await rzp.orders.create({ amount: total });\n+const order = await rzp.orders.create({ amount: Math.round(total * 100), currency: \"INR\" });",
    timestamp: "1m ago",
    status: "merged",
    usagesPatched: 3,
  },
  {
    id: "2",
    package: "razorpay / webhook",
    oldVersion: "hmac_mismatch",
    newVersion: "ci-verified",
    diff: "-const valid = validateWebhook(body, sig);\n+const valid = validateWebhookSignature(body, sig, process.env.RAZORPAY_WEBHOOK_SECRET);",
    timestamp: "8m ago",
    status: "merged",
    usagesPatched: 1,
  },
  {
    id: "3",
    package: "razorpay / timeout",
    oldVersion: "network_error",
    newVersion: "recovered (₹500.00)",
    diff: "// Bounded backoff retry succeeded on attempt 2\n// Outcome: recovered | Revenue collected: ₹500.00 (50000 paise)",
    timestamp: "19m ago",
    status: "merged",
    usagesPatched: 1,
  },
  {
    id: "4",
    package: "razorpay-node",
    oldVersion: "v2.8.0",
    newVersion: "v2.9.2",
    diff: "-const client = new Razorpay(key, secret);\n+const client = new Razorpay({ key_id: key, key_secret: secret });",
    timestamp: "45m ago",
    status: "merged",
    usagesPatched: 4,
  },
  {
    id: "5",
    package: "aura-drops / checkout",
    oldVersion: "runtime_defect",
    newVersion: "ci-verified",
    diff: "-const res = await rzp.payments.capture(paymentId, amount);\n+const res = await rzp.payments.capture(paymentId, amount, \"INR\");",
    timestamp: "2h ago",
    status: "open",
    usagesPatched: 2,
  },
];

function renderDiffLine(line: string) {
  const chars = line.split("").map((char, i) => (
    <span key={i} className="char">
      {char}
    </span>
  ));

  if (line.startsWith("-")) {
    return (
      <div key={line} className="text-xs font-mono leading-relaxed text-white/50 bg-white/[0.03] px-3 py-0.5 rounded-lg">
        {chars}
      </div>
    );
  }
  if (line.startsWith("+")) {
    return (
      <div key={line} className="text-xs font-mono leading-relaxed text-white font-medium bg-white/[0.08] px-3 py-0.5 rounded-lg">
        {chars}
      </div>
    );
  }
  return (
    <div key={line} className="text-xs font-mono leading-relaxed text-[#888888] px-3 py-0.5">
      {chars}
    </div>
  );
}

function Ticket({ ticket, index }: { ticket: TicketData; index: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const diffRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (diffRef.current && !prefersReducedMotion()) {
      const chars = diffRef.current.querySelectorAll(".char");
      const delay = index * 60 + 350;
      setTimeout(() => {
        animateDiffReveal(chars as NodeListOf<Element>);
      }, delay);
    }
  }, [index]);

  return (
    <div
      ref={ref}
      className="patch-ticket w-full max-w-xl mx-auto opacity-0 transition-all duration-300 hover:border-white/25 hover:bg-white/[0.03] shadow-xl overflow-hidden bg-white/[0.015] border border-white/10 backdrop-blur-2xl rounded-2xl p-1"
      style={{ transform: "translateY(-24px)" }}
    >
      <div className="px-5 pt-3.5 pb-2 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="font-mono text-[10px] text-[#888888] uppercase tracking-wider bg-white/[0.04] px-2 py-0.5 rounded-full font-medium border border-white/10">
            PATCH
          </span>
          <span className="font-mono text-sm font-semibold text-white tracking-tight">
            {ticket.package}
          </span>
          <span className="font-mono text-xs text-[#888888]">
            {ticket.oldVersion} → <span className="text-white">{ticket.newVersion}</span>
          </span>
        </div>
        <div className="flex items-center gap-3">
          <Badge status={ticket.status} />
          <span className="font-mono text-[10px] text-[#888888]">
            {ticket.timestamp}
          </span>
        </div>
      </div>

      {/* Diff lines container (Rounded-xl) */}
      <div
        ref={diffRef}
        className="font-mono px-4 py-3 mx-2 rounded-xl border border-white/[0.06] bg-black/80 flex flex-col gap-1 my-1"
        style={{ fontSize: "11px" }}
      >
        {ticket.diff.split("\n").map((line, i) => (
          <div key={i}>{renderDiffLine(line)}</div>
        ))}
      </div>

      <div className="px-5 py-2.5 flex items-center justify-between">
        <span
          className="font-mono text-[11px] flex items-center gap-1.5 font-medium text-white/90"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-white inline-block shadow-[0_0_6px_#ffffff]" />
          {ticket.usagesPatched} call site{ticket.usagesPatched !== 1 ? "s" : ""} auto-patched
        </span>

        <span className="font-mono text-[10px] text-[#8E8E93] uppercase tracking-widest">
          CI GATED // VERIFIED AST
        </span>
      </div>
    </div>
  );
}

export default function TicketFeed() {
  const feedRef = useRef<HTMLDivElement>(null);
  const [tickets] = useState(DEMO_TICKETS);

  useEffect(() => {
    if (!feedRef.current) return;
    const cards = feedRef.current.querySelectorAll(".patch-ticket");
    animateTicketIn(cards as NodeListOf<Element>);
  }, []);

  return (
    <div className="flex flex-col gap-3.5 w-full" ref={feedRef}>
      {tickets.map((t, i) => (
        <Ticket key={t.id} ticket={t} index={i} />
      ))}
    </div>
  );
}

"use client";

import { useState } from "react";

const STEPS = [
  {
    tag: "01 // DETECT",
    title: "Continuous Registry Watcher",
    description:
      "Telex monitors npm releases in real time. The moment a new version publishes, it diffs exported public interfaces and extracts structured breaking changes.",
    code: `// Detected: openai@4.0.0
{
  change: "signature_change",
  symbol_old: "createCompletion()",
  symbol_new: "completions.create()",
  confidence: 0.97
}`,
  },
  {
    tag: "02 // SCAN",
    title: "Syntax-Aware Tree-Sitter AST",
    description:
      "For every watching repository, Telex parses the TypeScript/JavaScript AST to pinpoint exact call sites across your entire codebase. Zero regex heuristics.",
    code: `// Found 6 usages in repo
src/lib/ai.ts         (L42, L87)
src/routes/chat.ts    (L19)
src/workers/embed.ts  (L31, L66)`,
  },
  {
    tag: "03 // PATCH",
    title: "Validated Unified Diff PR",
    description:
      "Generates minimal unified diffs tailored to your exact call sites. Every patch passes a deterministic validation gate before bundling into a pull request.",
    code: `-const r = await client.createCompletion(p);
+const r = await client.completions.create(p);`,
  },
];

export default function HowItWorks() {
  const [activeStep, setActiveStep] = useState<number | null>(null);

  return (
    <section id="how-it-works" className="py-28 px-6 sm:px-10 bg-black border-t border-white/[0.08]">
      <div className="max-w-6xl mx-auto">
        {/* Section Header */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-14 pb-6 border-b border-white/[0.08]">
          <div>
            <span className="font-mono text-[10px] tracking-[0.25em] text-[#8E8E93] uppercase block mb-2 font-medium">
              [ PIPELINE ARCHITECTURE // 01-03 ]
            </span>
            <h2 className="font-header font-bold text-3xl md:text-5xl text-white tracking-[-0.035em]">
              Three steps.{" "}
              <span className="text-silver-gradient">
                No magic.
              </span>
            </h2>
          </div>
          <p className="font-sans text-xs sm:text-sm text-[#9E9E9E] max-w-sm leading-relaxed">
            Deterministic, verifiable dependency migration from package publish to submitted pull request.
          </p>
        </div>

        {/* 3-Column Architectural Grid with Shallow/Hollow Rounded-3xl Cards */}
        <div className="grid md:grid-cols-3 gap-5">
          {STEPS.map((step, idx) => (
            <div
              key={step.tag}
              onMouseEnter={() => setActiveStep(idx)}
              onMouseLeave={() => setActiveStep(null)}
              className={`p-8 rounded-3xl flex flex-col justify-between gap-6 transition-all duration-300 relative overflow-hidden backdrop-blur-xl border ${
                activeStep === idx
                  ? "bg-white/[0.04] border-white/30 shadow-[0_12px_32px_rgba(255,255,255,0.06)] -translate-y-1"
                  : "bg-white/[0.015] border-white/10"
              }`}
            >
              <div>
                <span
                  className={`font-mono text-[10px] tracking-[0.2em] block mb-3 font-bold transition-colors duration-300 ${
                    activeStep === idx ? "text-white" : "text-[#71717A]"
                  }`}
                >
                  [{step.tag}]
                </span>
                <h3 className="font-header font-bold text-xl text-white tracking-tight mb-3">
                  {step.title}
                </h3>
                <p className="font-sans text-xs sm:text-sm text-[#9E9E9E] leading-relaxed">
                  {step.description}
                </p>
              </div>

              {/* Code snippet block */}
              <div
                className={`font-mono text-[11px] p-4 rounded-2xl bg-black/80 border transition-all duration-300 text-white leading-relaxed overflow-x-auto mt-4 relative ${
                  activeStep === idx ? "border-white/30 shadow-[0_0_20px_rgba(255,255,255,0.05)]" : "border-white/[0.08]"
                }`}
                style={{ whiteSpace: "pre" }}
              >
                {step.code.split("\n").map((line, i) => (
                  <div
                    key={i}
                    className={
                      line.startsWith("-")
                        ? "text-white/40 bg-white/[0.03] px-1 rounded-sm"
                        : line.startsWith("+")
                        ? "text-white font-bold bg-white/[0.08] px-1 rounded-sm"
                        : "text-[#71717A]"
                    }
                  >
                    {line}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

"use client";

import { useState } from "react";


const STEPS = [
  {
    tag: "01 // DETECT",
    title: "Registry Monitoring & Breaking Change Detection",
    description:
      "Telex polls npm and PyPI for new package versions. When a new version ships, it extracts the changelog and uses Gemini to identify renamed, removed, or signature-changed symbols.",
    code: `// Detected Change Schema
{
  "source": "npm_registry",
  "symbol_old": "createClient",
  "change_type": "signature_change",
  "confidence": 0.97
}`,
  },
  {
    tag: "02 // SCAN & PATCH",
    title: "AST-Precise Call-Site Scanning & Gemini Patch Synthesis",
    description:
      "Tree-sitter parses every TypeScript and Python file in the repo. Only files that actually call the changed symbol are targeted. Gemini synthesizes a minimal unified diff.",
    code: `// Unified Diff Synthesis
-const client = createClient(config);
+const client = createClient({
+  ...config,
+  timeout: config.timeout ?? 5000
+});`,
  },
  {
    tag: "03 // VERIFY & PR",
    title: "Ephemeral CI Gate & Human-Reviewed Pull Request",
    description:
      "The patch runs through an isolated GitHub Actions gate (real install, tsc, and test suite) before a pull request is opened. Nothing merges automatically — a human always reviews.",
    code: `# Ephemeral Native CI Gate
steps:
  - run: npm ci
  - run: npx tsc --noEmit
  - run: npm test
# Gate: repo CI proved green`,
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
              [ TELEX PIPELINE // 01-03 ]
            </span>
            <h2 className="font-header font-bold text-3xl md:text-5xl text-white tracking-[-0.035em]">
              Three steps.{" "}
              <span className="text-silver-gradient">
                Zero broken builds.
              </span>
            </h2>
          </div>
          <p className="font-sans text-xs sm:text-sm text-[#9E9E9E] max-w-sm leading-relaxed">
            From upstream SDK break to CI-verified pull request — fully automated, human-reviewed.
          </p>
        </div>

        {/* 3-Column Architectural Grid with Realistic Machined Modules */}
        <div className="grid md:grid-cols-3 gap-5">
          {STEPS.map((step, idx) => (
            <div
              key={step.tag}
              onMouseEnter={() => setActiveStep(idx)}
              onMouseLeave={() => setActiveStep(null)}
              className={`metal-bezel p-[2px] rounded-2xl transition-all duration-300 relative ${
                activeStep === idx ? "-translate-y-1 shadow-[0_16px_40px_rgba(0,0,0,0.9)] brightness-105" : "shadow-xl"
              }`}
            >
              {/* Corner rivets */}
              <span className="absolute top-2.5 left-2.5 w-1.5 h-1.5 rounded-full bg-[#3F3F46] shadow-[inset_0_1px_1px_rgba(255,255,255,0.3),0_1px_0_rgba(0,0,0,0.8)] z-10 pointer-events-none" />
              <span className="absolute top-2.5 right-2.5 w-1.5 h-1.5 rounded-full bg-[#3F3F46] shadow-[inset_0_1px_1px_rgba(255,255,255,0.3),0_1px_0_rgba(0,0,0,0.8)] z-10 pointer-events-none" />
              <span className="absolute bottom-2.5 left-2.5 w-1.5 h-1.5 rounded-full bg-[#3F3F46] shadow-[inset_0_1px_1px_rgba(255,255,255,0.3),0_1px_0_rgba(0,0,0,0.8)] z-10 pointer-events-none" />
              <span className="absolute bottom-2.5 right-2.5 w-1.5 h-1.5 rounded-full bg-[#3F3F46] shadow-[inset_0_1px_1px_rgba(255,255,255,0.3),0_1px_0_rgba(0,0,0,0.8)] z-10 pointer-events-none" />

              <div className="panel-inset p-7 rounded-[14px] flex flex-col justify-between gap-6 h-full relative">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <span className="badge-chip px-2.5 py-1 text-[10px] font-mono font-bold flex items-center gap-1.5">
                      <span className="led" data-state={idx === 2 ? "ok" : "busy"} />
                      <span>{step.tag}</span>
                    </span>
                    <span className="font-mono text-[10px] text-[#52525B]">STAGE 0{idx + 1}</span>
                  </div>

                  <h3 className="font-header font-bold text-xl text-white tracking-tight mb-3 label-embossed">
                    {step.title}
                  </h3>
                  <p className="font-sans text-xs sm:text-sm text-[#9E9E9E] leading-relaxed">
                    {step.description}
                  </p>
                </div>

                {/* Recessed CRT Terminal Screen */}
                <div
                  className="font-mono text-[11px] p-4 rounded-xl glass-bezel text-white leading-relaxed overflow-x-auto relative"
                  style={{ whiteSpace: "pre" }}
                >
                  {step.code.split("\n").map((line, i) => (
                    <div
                      key={i}
                      className={
                        line.startsWith("-")
                          ? "text-[#FDA4AF] bg-[#E11D48]/10 px-1 rounded-sm"
                          : line.startsWith("+")
                          ? "text-[#5EEAD4] font-bold bg-[#14B8A6]/15 px-1 rounded-sm"
                          : "text-[#71717A]"
                      }
                    >
                      {line}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

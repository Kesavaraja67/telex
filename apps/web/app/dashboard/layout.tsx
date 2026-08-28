"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "motion/react";
import TelexLogo from "@/components/ui/TelexLogo";

const NAV_ITEMS = [
  {
    href: "/dashboard",
    label: "Overview",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
      </svg>
    ),
  },
  {
    href: "/dashboard/recovery",
    label: "Payment Recovery",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
  },
  {
    href: "/dashboard/settings",
    label: "Settings",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
      </svg>
    ),
  },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div className="flex min-h-screen bg-black text-[#F2F1ED] font-sans antialiased selection:bg-white/20 selection:text-white">
      {/* Sidebar */}
      <aside className="w-64 flex-shrink-0 flex flex-col py-6 px-4 bg-black/90 backdrop-blur-2xl border-r border-white/[0.08] relative z-20">
        {/* Brand header with Minimalist Bold White T Logo */}
        <Link
          href="/"
          className="font-mono font-bold tracking-[0.25em] text-sm text-[#F2F1ED] hover:text-white transition-colors mb-8 px-3 flex items-center gap-2.5 group"
        >
          <TelexLogo size={20} withBackground={true} />
          <span className="tracking-widest">TELEX</span>
          <span className="font-mono text-[9px] bg-white/[0.06] text-[#7A7F87] px-1.5 py-0.5 rounded border border-white/5 ml-auto">
            v1.0
          </span>
        </Link>

        {/* Navigation links */}
        <nav className="flex flex-col gap-1.5">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`relative font-mono text-xs tracking-wide px-3.5 py-2.5 rounded-xl transition-all flex items-center gap-3 group ${
                  isActive
                    ? "text-white bg-white/[0.08] border border-white/15 shadow-[0_4px_20px_rgba(0,0,0,0.5)]"
                    : "text-[#A1A1AA] hover:text-white hover:bg-white/[0.04] border border-transparent"
                }`}
              >
                {isActive && (
                  <motion.div
                    layoutId="sidebar-active-indicator"
                    className="absolute left-0 top-2 bottom-2 w-1 rounded-r-full bg-white shadow-[0_0_8px_#FFFFFF]"
                    transition={{ type: "spring", stiffness: 380, damping: 30 }}
                  />
                )}
                <span className={`transition-colors ${isActive ? "text-white" : "text-[#71717A] group-hover:text-white"}`}>
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </Link>
            );
          })}

          {/* Quick link back to Landing Page */}
          <Link
            href="/"
            className="font-mono text-xs tracking-wide px-3.5 py-2.5 rounded-xl transition-all flex items-center gap-3 text-[#71717A] hover:text-white hover:bg-white/[0.04] border border-transparent mt-1 group"
          >
            <svg className="w-4 h-4 text-[#71717A] group-hover:text-white transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
            <span>Landing Page</span>
          </Link>
        </nav>

        {/* Connect Repository Sidebar Action */}
        <div className="pt-4">
          <a
            href={`https://github.com/apps/${process.env.NEXT_PUBLIC_GITHUB_APP_NAME || "telex-agent-dev"}/installations/new`}
            target="_blank"
            rel="noopener noreferrer"
            className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl bg-white text-black font-mono font-semibold text-xs transition-all hover:bg-white/90 hover:shadow-[0_0_15px_rgba(255,255,255,0.2)] active:scale-[0.98]"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            <span>Connect Repo</span>
          </a>
        </div>

        {/* Live Daemon Status Indicator */}
        <div className="mt-auto pt-6 border-t border-white/[0.08] flex flex-col gap-4">
          <div className="px-3.5 py-3 rounded-xl bg-black/60 border border-white/[0.06] flex items-center justify-between shadow-inner">
            <div className="flex items-center gap-2.5">
              <span className="w-2 h-2 rounded-full bg-white animate-pulse shadow-[0_0_8px_#FFFFFF]" />
              <span className="font-mono text-xs text-white font-medium">Worker Pool</span>
            </div>
            <span className="font-mono text-[10px] text-white px-2 py-0.5 rounded bg-white/10 border border-white/20 font-semibold">
              ACTIVE
            </span>
          </div>

          <div className="flex items-center justify-between px-3">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-white/10 border border-white/20 flex items-center justify-center font-mono text-xs font-semibold text-white">
                TX
              </div>
              <div className="flex flex-col">
                <span className="font-mono text-xs font-medium text-white">GitHub App</span>
                <span className="font-mono text-[10px] text-[#71717A]">Connected</span>
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto bg-black relative">
        <div className="max-w-6xl mx-auto px-8 py-10 relative z-10">{children}</div>
      </main>
    </div>
  );
}

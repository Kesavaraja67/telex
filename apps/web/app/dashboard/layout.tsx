import type { Metadata } from "next";
import Link from "next/link";
import TelexLogo from "@/components/ui/TelexLogo";

export const metadata: Metadata = {
  title: "Dashboard | Telex",
};

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen bg-black text-[#F2F1ED]">
      {/* Sidebar */}
      <aside className="w-64 flex-shrink-0 flex flex-col py-6 px-4 bg-black border-r border-white/[0.08]">
        {/* Brand header with Minimalist Bold White T Logo */}
        <Link
          href="/"
          className="font-mono font-bold tracking-[0.25em] text-sm text-[#F2F1ED] hover:text-white transition-colors mb-8 px-3 flex items-center gap-2.5 group"
        >
          <TelexLogo size={20} withBackground={true} />
          <span>TELEX</span>
          <span className="font-mono text-[9px] bg-white/[0.06] text-[#7A7F87] px-1.5 py-0.5 rounded ml-auto">
            v1.0
          </span>
        </Link>

        {/* Navigation links */}
        <nav className="flex flex-col gap-1">
          {[
            { href: "/dashboard", label: "Overview", icon: "⌘" },
            { href: "/dashboard/repos", label: "Watched Repos", icon: "⎇" },
            { href: "/dashboard/settings", label: "Settings", icon: "⚙" },
          ].map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="font-mono text-xs tracking-wide px-3.5 py-2.5 rounded-lg transition-all text-[#7A7F87] hover:text-[#F2F1ED] hover:bg-white/[0.04] flex items-center gap-3 group"
            >
              <span className="text-sm opacity-60 group-hover:opacity-100 transition-opacity">
                {item.icon}
              </span>
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>

        {/* Live Daemon Status Indicator */}
        <div className="mt-auto pt-6 border-t border-white/[0.08] flex flex-col gap-4">
          <div className="px-3 py-2.5 rounded-lg glass-surface-subtle border border-white/[0.06] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#4FD1C5] animate-pulse shadow-[0_0_8px_#4FD1C5]" />
              <span className="font-mono text-[11px] text-[#F2F1ED]">Worker Pool</span>
            </div>
            <span className="font-mono text-[10px] text-[#4FD1C5]">ACTIVE</span>
          </div>

          <div className="flex items-center justify-between px-3">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-[#4FD1C5]/30 to-white/10 border border-white/20 flex items-center justify-center font-mono text-xs font-semibold text-[#F2F1ED]">
                TX
              </div>
              <div className="flex flex-col">
                <span className="font-mono text-xs font-medium text-[#F2F1ED]">GitHub App</span>
                <span className="font-mono text-[10px] text-[#7A7F87]">Connected</span>
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto bg-black">
        <div className="max-w-6xl mx-auto px-8 py-10">{children}</div>
      </main>
    </div>
  );
}

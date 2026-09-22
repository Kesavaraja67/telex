"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "motion/react";
import TelexLogo from "@/components/ui/TelexLogo";
import CyberGridBackground from "@/components/ui/CyberGridBackground";
import { getApiUrl } from "@/lib/api";
import { SidebarProvider, useSidebar } from "@/components/dashboard/SidebarContext";

interface AuthUser {
  id?: string;
  github_login: string;
  email?: string | null;
  avatar_url?: string | null;
}

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
    href: "/dashboard/repos",
    label: "Repositories",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
      </svg>
    ),
  },
  {
    href: "/dashboard/atlas",
    label: "Repo Atlas",
    icon: (
      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75}>
        <circle cx="12" cy="5" r="2" />
        <circle cx="5" cy="19" r="2" />
        <circle cx="19" cy="19" r="2" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 7v5m0 0l-5.5 5m5.5-5l5.5 5" />
      </svg>
    ),
  },
  {
    href: "/dashboard/activity",
    label: "Activity Feed",
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

function DashboardContent({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authStatus, setAuthStatus] = useState<"checking" | "authenticated" | "unauthenticated">("checking");
  const [isLocalhost, setIsLocalhost] = useState(false);
  const { isSidebarCollapsed, toggleSidebar } = useSidebar();

  useEffect(() => {
    if (typeof window === "undefined") return;

    setIsLocalhost(
      window.location.hostname === "localhost" ||
      window.location.hostname === "127.0.0.1"
    );

    // Extract token from URL hash (#token=...)
    let tokenFromUrl: string | null = null;
    if (window.location.hash) {
      const hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ""));
      tokenFromUrl = hashParams.get("token");
    }

    if (tokenFromUrl) {
      localStorage.setItem("telex_token", tokenFromUrl);
    }

    // Remove only credentials/hash from address bar; keep other parameters like ?repo=...
    if (tokenFromUrl || window.location.hash) {
      const remaining = new URLSearchParams(window.location.search);
      remaining.delete("token");
      const qs = remaining.toString();
      const cleanUrl = window.location.pathname + (qs ? `?${qs}` : "");
      window.history.replaceState({}, document.title, cleanUrl);
    }

    const apiUrl = getApiUrl();
    const token = localStorage.getItem("telex_token");
    const headers: Record<string, string> = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    // Validate session against backend /api/auth/me via Bearer header and HttpOnly cookie
    fetch(`${apiUrl}/api/auth/me`, {
      credentials: "include",
      headers,
    })
      .then((res) => {
        if (!res.ok) throw new Error("Auth request failed");
        return res.json();
      })
      .then((data) => {
        if (data.authenticated && data.user) {
          setUser(data.user);
          if (data.user.github_login) {
            localStorage.setItem("telex_user", data.user.github_login);
          }
          setAuthStatus("authenticated");
        } else {
          setUser(null);
          localStorage.removeItem("telex_token");
          localStorage.removeItem("telex_user");
          setAuthStatus("unauthenticated");
        }
      })
      .catch(() => {
        setUser(null);
        setAuthStatus("unauthenticated");
      });
  }, []);

  const handleSignOut = async () => {
    localStorage.removeItem("telex_token");
    localStorage.removeItem("telex_user");
    const apiUrl = getApiUrl();
    try {
      await fetch(`${apiUrl}/api/auth/logout`, {
        method: "POST",
        credentials: "include",
        headers: { Accept: "application/json" },
      });
    } catch {
      // Ignore network errors on logout
    }
    window.location.href = "/";
  };

  // ── 1. Checking Session Loading Screen ─────────────────────────────────────
  if (authStatus === "checking") {
    return (
      <div
        className="flex min-h-screen bg-black items-center justify-center font-mono"
        role="status"
        aria-label="Loading dashboard"
      >
        <div className="flex flex-col items-center gap-3 animate-fade-in">
          <TelexLogo size={32} withBackground={true} className="animate-pulse" />
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 border-2 border-white/20 border-t-white rounded-full animate-spin" />
            <span className="text-xs text-[#71717A] tracking-wider uppercase">
              Loading dashboard...
            </span>
          </div>
        </div>
      </div>
    );
  }

  // ── 2. Auth Wall (Restricted Access) ───────────────────────────────────────
  if (authStatus === "unauthenticated") {
    const apiUrl = getApiUrl();

    return (
      <div className="flex min-h-screen bg-black text-[#F2F1ED] items-center justify-center p-6 relative overflow-hidden font-sans">
        <CyberGridBackground />
        <div className="relative z-10 max-w-md w-full p-8 rounded-2xl border border-white/10 bg-black/85 backdrop-blur-2xl shadow-[0_8px_32px_rgba(0,0,0,0.8)] text-center flex flex-col items-center gap-6">
          <TelexLogo size={44} withBackground={true} />
          
          <div className="flex flex-col items-center gap-2">
            <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-[#A1A1AA] px-3 py-1 rounded-full border border-white/10 bg-white/[0.04]">
              Authentication Required
            </span>
            <h2 className="font-mono text-xl font-bold text-white tracking-tight">
              Telex Command Deck
            </h2>
            <p className="font-sans text-xs text-[#8E8E93] leading-relaxed max-w-sm">
              Autonomous AST scanning, repository fleet telemetry, and patch verification require an authenticated GitHub operator session.
            </p>
          </div>

          <div className="flex flex-col w-full gap-3">
            <button
              id="auth-guard-devlogin-btn"
              onClick={() => {
                window.location.href = `${apiUrl}/api/auth/dev-login`;
              }}
              className="w-full py-2.5 px-4 rounded-xl bg-white text-black font-mono font-semibold text-xs tracking-wider uppercase transition-all hover:bg-white/90 hover:shadow-[0_0_20px_rgba(255,255,255,0.3)] active:scale-[0.98] flex items-center justify-center gap-2 cursor-pointer"
            >
              <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24">
                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
              </svg>
              <span>Sign In as Operator (Instant Localhost) &rarr;</span>
            </button>

            <button
              id="auth-guard-signin-btn"
              onClick={() => {
                const origin = encodeURIComponent(window.location.origin);
                window.location.href = `${apiUrl}/api/auth/github?origin=${origin}`;
              }}
              className="w-full py-2.5 px-4 rounded-xl border border-white/20 text-white hover:bg-white/[0.08] font-mono text-xs tracking-wider transition-all flex items-center justify-center gap-2 cursor-pointer"
            >
              <svg className="w-4 h-4 fill-current" viewBox="0 0 24 24">
                <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
              </svg>
              <span>Sign in with GitHub OAuth</span>
            </button>

            <Link
              href="/"
              className="w-full py-2 text-center font-mono text-xs text-[#71717A] hover:text-white transition-colors"
            >
              ← Return to Landing Page
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // ── 3. Authenticated Dashboard Layout ───────────────────────────────────────
  return (
    <div className="flex min-h-screen bg-black text-[#F2F1ED] font-sans antialiased selection:bg-white/20 selection:text-white relative">
        {/* Floating Expand Sidebar Button (Shown when sidebar is collapsed) */}
        {isSidebarCollapsed && (
          <motion.div
            initial={{ opacity: 0, x: -12, scale: 0.95 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: -12, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            className="fixed top-3 left-3 z-50 flex items-center"
          >
            <button
              type="button"
              id="expand-sidebar-btn"
              onClick={toggleSidebar}
              title="Expand sidebar (Normal view) [Ctrl+B]"
              aria-label="Expand sidebar"
              className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-black/90 hover:bg-black text-[#A1A1AA] hover:text-white border border-white/20 hover:border-white/40 backdrop-blur-2xl shadow-[0_8px_32px_rgba(0,0,0,0.8)] font-mono text-xs transition-all hover:scale-105 active:scale-95 cursor-pointer group"
            >
              <TelexLogo size={16} withBackground={true} />
              <svg
                className="w-3.5 h-3.5 text-[#71717A] group-hover:text-white transition-colors"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={1.75}
              >
                <rect x="3" y="3" width="18" height="18" rx="2" strokeWidth={1.75} />
                <path d="M9 3v18" strokeWidth={1.75} />
                <path d="M13 9l3 3-3 3" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <span className="text-[11px] text-white font-semibold tracking-wider">TELEX</span>
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-white/10 text-[#A1A1AA] group-hover:text-white border border-white/5 uppercase">
                Expand
              </span>
            </button>
          </motion.div>
        )}

        {/* Sidebar */}
        <aside
          className={`flex-shrink-0 flex flex-col bg-black/90 backdrop-blur-2xl border-r border-white/[0.08] relative z-30 transition-all duration-300 ease-in-out ${
            isSidebarCollapsed
              ? "w-0 p-0 border-r-transparent overflow-hidden opacity-0 pointer-events-none"
              : "w-64 py-6 px-4 opacity-100"
          }`}
        >
          <div className="w-56 flex flex-col h-full">
            {/* Brand header with Minimalist Bold White T Logo & Collapse button */}
            <div className="flex items-center justify-between mb-8 px-1">
              <Link
                href="/"
                className="font-mono font-bold tracking-[0.25em] text-sm text-[#F2F1ED] hover:text-white transition-colors flex items-center gap-2 group"
              >
                <TelexLogo size={20} withBackground={true} />
                <span className="tracking-widest">TELEX</span>
                <span className="font-mono text-[9px] bg-white/[0.06] text-[#7A7F87] px-1.5 py-0.5 rounded border border-white/5">
                  v1.0
                </span>
              </Link>

              <button
                type="button"
                id="collapse-sidebar-btn"
                onClick={toggleSidebar}
                title="Collapse sidebar to full screen [Ctrl+B]"
                aria-label="Collapse sidebar"
                className="p-1.5 rounded-lg text-[#71717A] hover:text-white hover:bg-white/[0.08] transition-colors cursor-pointer group"
              >
                <svg
                  className="w-4 h-4 text-[#71717A] group-hover:text-white transition-colors"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={1.75}
                >
                  <rect x="3" y="3" width="18" height="18" rx="2" strokeWidth={1.75} />
                  <path d="M9 3v18" strokeWidth={1.75} />
                  <path d="M15 9l-3 3 3 3" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>

            {/* Navigation links */}
            <nav className="flex flex-col gap-1.5">
              {NAV_ITEMS.map((item) => {
                const isActive =
                  item.href === "/dashboard"
                    ? pathname === "/dashboard"
                    : pathname === item.href || pathname.startsWith(item.href + "/");
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

            {/* User Profile & Daemon Status Footer */}
            <div className="mt-auto pt-6 border-t border-white/[0.08] flex flex-col gap-3">
              {/* Authenticated User Info */}
              <div className="px-3.5 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] flex items-center justify-between">
                <div className="flex items-center gap-2.5 overflow-hidden">
                  {user?.avatar_url ? (
                    <img
                      src={user.avatar_url}
                      alt={user.github_login}
                      className="w-7 h-7 rounded-lg border border-white/20 object-cover shrink-0"
                    />
                  ) : (
                    <div className="w-7 h-7 rounded-lg bg-white/10 border border-white/20 flex items-center justify-center font-mono text-xs font-semibold text-white shrink-0">
                      {user?.github_login ? user.github_login.slice(0, 2).toUpperCase() : "TX"}
                    </div>
                  )}
                  <div className="flex flex-col min-w-0">
                    <span className="font-mono text-xs font-medium text-white truncate">
                      {user?.github_login || "Operator"}
                    </span>
                    <span className="font-mono text-[9px] text-[#71717A] tracking-wider uppercase">
                      Connected
                    </span>
                  </div>
                </div>

                <button
                  onClick={handleSignOut}
                  title="Sign Out"
                  className="p-1.5 rounded-lg text-[#71717A] hover:text-white hover:bg-white/[0.08] transition-colors cursor-pointer shrink-0"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                  </svg>
                </button>
              </div>

              {/* Worker Pool Status */}
              <div className="px-3 py-2 rounded-lg bg-black/40 border border-white/[0.04] flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse shadow-[0_0_6px_#FFFFFF]" />
                  <span className="font-mono text-[11px] text-[#A1A1AA]">Radar Daemon</span>
                </div>
                <span className="font-mono text-[9px] text-white px-1.5 py-0.5 rounded bg-white/10 border border-white/20 font-medium">
                  READY
                </span>
              </div>
            </div>
          </div>
        </aside>

        {/* Main content */}
        <main
          className={`flex-1 ${
            pathname.startsWith("/dashboard/atlas") ? "overflow-hidden h-screen" : "overflow-auto"
          } bg-black relative transition-all duration-300`}
        >
          <div
            className={
              pathname.startsWith("/dashboard/atlas")
                ? "w-full h-full relative"
                : "max-w-6xl mx-auto px-8 py-10 relative z-10"
            }
          >
            {children}
          </div>
        </main>
      </div>
  );
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <SidebarProvider>
      <DashboardContent>{children}</DashboardContent>
    </SidebarProvider>
  );
}

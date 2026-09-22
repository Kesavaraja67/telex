"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import TelexLogo from "@/components/ui/TelexLogo";
import { getApiUrl } from "@/lib/api";

const NAV_LINKS = [
  { href: "#how-it-works", label: "01 // Pipeline" },
  { href: "/dashboard", label: "02 // Dashboard" },
];

export default function Nav() {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);
  const [user, setUser] = useState<string | null>(null);

  useEffect(() => {
    const apiUrl = getApiUrl();
    const token = typeof window !== "undefined" ? localStorage.getItem("telex_token") : null;
    const headers: Record<string, string> = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    fetch(`${apiUrl}/api/auth/me`, { credentials: "include", headers })
      .then((res) => {
        if (!res.ok) throw new Error("Auth check failed");
        return res.json();
      })
      .then((data) => {
        if (data.authenticated && data.user?.github_login) {
          setUser(data.user.github_login);
          localStorage.setItem("telex_user", data.user.github_login);
        } else {
          setUser(null);
        }
      })
      .catch(() => {
        const cached = typeof window !== "undefined" ? localStorage.getItem("telex_user") : null;
        setUser(cached);
      });
  }, []);

  const handleAuthAction = () => {
    const apiUrl = getApiUrl();
    if (user) {
      window.location.href = "/dashboard";
    } else {
      // In local development, use dev-login directly so developer isn't sent to production OAuth
      if (typeof window !== "undefined" && window.location.hostname === "localhost") {
        window.location.href = `${apiUrl}/api/auth/dev-login`;
        return;
      }
      const origin = typeof window !== "undefined" ? encodeURIComponent(window.location.origin) : "";
      window.location.href = `${apiUrl}/api/auth/github?origin=${origin}`;
    }
  };

  const handleSignOut = async (e: React.MouseEvent) => {
    e.stopPropagation();
    localStorage.removeItem("telex_token");
    localStorage.removeItem("telex_user");
    setUser(null);
    const apiUrl = getApiUrl();
    try {
      await fetch(`${apiUrl}/api/auth/logout`, {
        method: "POST",
        credentials: "include",
        headers: { Accept: "application/json" },
      });
    } catch {
      // Ignore network errors
    }
    window.location.reload();
  };

  return (
    <header className="fixed top-5 left-0 right-0 z-50 px-4 sm:px-8 pointer-events-none">
      <div className="max-w-5xl mx-auto flex items-center justify-between gap-4 px-6 py-2.5 rounded-full border border-white/10 bg-black/65 backdrop-blur-2xl shadow-[0_8px_32px_rgba(0,0,0,0.6)] pointer-events-auto transition-all duration-300 hover:border-white/20">
        {/* Brand wordmark with Minimalist Bold White T Logo */}
        <Link
          href="/"
          className="font-display font-bold text-sm tracking-[0.25em] text-white hover:text-white/90 transition-colors flex items-center gap-2.5 uppercase group shrink-0 whitespace-nowrap"
        >
          <TelexLogo size={20} withBackground={true} />
          <span>TELEX</span>
        </Link>

        {/* Nav links */}
        <div className="hidden md:flex items-center gap-6 lg:gap-8 font-mono text-[11px] uppercase tracking-[0.18em] text-[#888888] shrink-0 whitespace-nowrap">
          {NAV_LINKS.map((link, idx) => (
            <Link
              key={link.href}
              href={link.href}
              onMouseEnter={() => setHoveredIdx(idx)}
              onMouseLeave={() => setHoveredIdx(null)}
              className="relative h-5 overflow-hidden flex flex-col justify-center transition-colors whitespace-nowrap select-none shrink-0"
            >
              <span
                className="transition-transform duration-300 ease-[cubic-bezier(0.25,1,0.5,1)] whitespace-nowrap block leading-5"
                style={{
                  transform: hoveredIdx === idx ? "translateY(-140%)" : "translateY(0%)",
                  color: hoveredIdx === idx ? "#FFFFFF" : "#888888",
                }}
              >
                {link.label}
              </span>
              <span
                className="absolute transition-transform duration-300 ease-[cubic-bezier(0.25,1,0.5,1)] text-white font-medium whitespace-nowrap block leading-5"
                style={{
                  transform: hoveredIdx === idx ? "translateY(0%)" : "translateY(140%)",
                }}
              >
                {link.label}
              </span>
            </Link>
          ))}
        </div>

        {/* Sign In / User Dashboard CTA */}
        {user ? (
          <div className="flex items-center gap-2 shrink-0">
            <button
              id="nav-signin-btn"
              onClick={handleAuthAction}
              className="font-mono text-[10px] uppercase tracking-[0.18em] px-3.5 sm:px-4 py-2 rounded-full border border-white/20 hover:border-white text-white hover:bg-white/[0.08] backdrop-blur-md transition-all active:scale-95 cursor-pointer shadow-sm flex items-center gap-2 whitespace-nowrap"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
              <span>{`${user} // Deck →`}</span>
            </button>
            <button
              onClick={handleSignOut}
              title="Sign Out"
              aria-label="Sign Out"
              className="p-2 rounded-full border border-white/15 text-[#71717A] hover:text-white hover:border-white/30 hover:bg-white/[0.08] transition-all cursor-pointer"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
            </button>
          </div>
        ) : (
          <button
            id="nav-signin-btn"
            onClick={handleAuthAction}
            className="font-mono text-[10px] uppercase tracking-[0.18em] px-4 sm:px-5 py-2 rounded-full border border-white/20 hover:border-white text-white hover:bg-white/[0.08] backdrop-blur-md transition-all active:scale-95 cursor-pointer shadow-sm flex items-center gap-2 shrink-0 whitespace-nowrap"
          >
            <span>Sign in →</span>
          </button>
        )}
      </div>
    </header>
  );
}

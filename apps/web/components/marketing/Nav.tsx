"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import TelexLogo from "@/components/ui/TelexLogo";
import { getApiUrl } from "@/lib/api";

const NAV_LINKS = [
  { href: "#how-it-works", label: "01 // Pipeline" },
  { href: "/dashboard", label: "02 // Dashboard" },
];

export default function Nav() {
  const router = useRouter();
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
      router.push("/dashboard");
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
      <div className="max-w-5xl mx-auto pointer-events-auto metal-bezel p-[2px] rounded-full overflow-hidden shadow-[0_12px_40px_rgba(0,0,0,0.85)]">
        <div className="panel-inset px-6 py-2 rounded-full flex items-center justify-between gap-4">
          {/* Brand wordmark with Minimalist Bold White T Logo */}
          <Link
            href="/"
            className="font-display font-bold text-sm tracking-[0.25em] text-white hover:text-white/90 transition-colors flex items-center gap-2.5 uppercase group shrink-0 whitespace-nowrap"
          >
            <TelexLogo size={20} withBackground={true} />
            <span className="label-embossed">TELEX</span>
          </Link>

          {/* Nav links */}
          <div className="hidden md:flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.18em] shrink-0 whitespace-nowrap">
            {NAV_LINKS.map((link, idx) => (
              <Link
                key={link.href}
                href={link.href}
                onMouseEnter={() => setHoveredIdx(idx)}
                onMouseLeave={() => setHoveredIdx(null)}
                className={`px-3.5 py-1.5 rounded-full transition-all select-none ${
                  hoveredIdx === idx
                    ? "bg-white/[0.08] text-white font-semibold shadow-inner"
                    : "text-[#A1A1AA] hover:text-white"
                }`}
              >
                <span>{link.label}</span>
              </Link>
            ))}
          </div>

          {/* Sign In / User Dashboard CTA */}
          {user ? (
            <div className="flex items-center gap-2 shrink-0">
              <button
                id="nav-signin-btn"
                onClick={handleAuthAction}
                className="key-cap key-cap--sm font-mono text-[10px] uppercase tracking-[0.18em] px-3.5 sm:px-4 py-1.5 flex items-center gap-2 whitespace-nowrap cursor-pointer"
              >
                <span className="led" data-state="ok" />
                <span>{`${user} // Deck →`}</span>
              </button>
              <button
                onClick={handleSignOut}
                title="Sign Out"
                aria-label="Sign Out"
                className="key-cap key-cap--sm p-2 flex items-center justify-center cursor-pointer text-[#71717A] hover:text-white"
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
              className="key-cap key-cap--sm key-cap--primary font-mono text-[10px] uppercase tracking-[0.18em] px-4 sm:px-5 py-1.5 flex items-center gap-2 shrink-0 whitespace-nowrap cursor-pointer"
            >
              <span className="led" data-state="ok" />
              <span>Sign in →</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
}

"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import TelexLogo from "@/components/ui/TelexLogo";

const NAV_LINKS = [
  { href: "#how-it-works", label: "01 // Pipeline" },
  { href: "/dashboard/recovery", label: "02 // Live Stream" },
  { href: "/dashboard", label: "03 // Dashboard" },
];

export default function Nav() {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);
  const [user, setUser] = useState<string | null>(null);

  useEffect(() => {
    // Check if session cookie exists
    const match = document.cookie.match(/telex_user=([^;]+)/);
    if (match) {
      setUser(decodeURIComponent(match[1]));
    }
  }, []);

  const handleAuthAction = () => {
    const apiUrl =
      process.env.NEXT_PUBLIC_API_URL ||
      (window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1"
        ? "https://telex-api.onrender.com"
        : "http://localhost:8000");
    if (user) {
      window.location.href = "/dashboard";
    } else {
      window.location.href = `${apiUrl}/api/auth/github`;
    }
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
          <span className="font-mono text-[9px] text-[#8E8E93] tracking-widest hidden lg:inline-block whitespace-nowrap">
            [ RAZORPAY 2026 ]
          </span>
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
        <button
          id="nav-signin-btn"
          onClick={handleAuthAction}
          className="font-mono text-[10px] uppercase tracking-[0.18em] px-4 sm:px-5 py-2 rounded-full border border-white/20 hover:border-white text-white hover:bg-white/[0.08] backdrop-blur-md transition-all active:scale-95 cursor-pointer shadow-sm flex items-center gap-2 shrink-0 whitespace-nowrap"
        >
          {user ? (
            <>
              <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
              <span>{user} // Dashboard →</span>
            </>
          ) : (
            <span>Sign in →</span>
          )}
        </button>
      </div>
    </header>
  );
}

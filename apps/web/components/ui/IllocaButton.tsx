"use client";

import React, { useState } from "react";

interface IllocaButtonProps {
  label: string;
  onClick?: () => void;
  variant?: "primary" | "secondary";
  className?: string;
  id?: string;
}

export default function IllocaButton({
  label,
  onClick,
  variant = "primary",
  className = "",
  id,
}: IllocaButtonProps) {
  const [isHovered, setIsHovered] = useState(false);

  const isPrimary = variant === "primary";

  return (
    <button
      id={id}
      onClick={onClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className={`group relative inline-flex items-center justify-center h-12 px-8 font-mono text-xs uppercase tracking-[0.2em] font-bold rounded-full overflow-hidden cursor-pointer transition-all duration-300 active:scale-[0.97] ${
        isPrimary
          ? "bg-white text-black border border-white hover:bg-[#ECE7DA] shadow-[0_0_30px_rgba(255,255,255,0.25)]"
          : "bg-white/[0.03] text-white border border-white/20 hover:border-white/60 hover:bg-white/[0.08] backdrop-blur-md shadow-[0_4px_20px_rgba(0,0,0,0.5)]"
      } ${className}`}
    >
      {/* Dual-layer rolling text container with spring physics */}
      <div className="relative h-4 overflow-hidden flex flex-col justify-center items-center pointer-events-none">
        <span
          className="transition-transform duration-300 ease-[cubic-bezier(0.25,1,0.5,1)]"
          style={{
            transform: isHovered ? "translateY(-130%)" : "translateY(0%)",
          }}
        >
          {label}
        </span>
        <span
          className="absolute transition-transform duration-300 ease-[cubic-bezier(0.25,1,0.5,1)]"
          style={{
            transform: isHovered ? "translateY(0%)" : "translateY(130%)",
            color: isPrimary ? "#000000" : "#FFFFFF",
          }}
        >
          {label}
        </span>
      </div>
    </button>
  );
}

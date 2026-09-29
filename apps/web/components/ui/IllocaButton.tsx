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
      className={`group relative inline-flex items-center justify-center h-12 px-8 font-mono text-xs uppercase tracking-[0.16em] font-semibold rounded-md overflow-hidden cursor-pointer select-none ${
        isPrimary ? "key-cap text-white" : "key-cap key-cap--ghost"
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
            color: "#FFFFFF",
          }}
        >
          {label}
        </span>
      </div>
    </button>
  );
}


"use client";

import React from "react";

interface TelexLogoProps {
  className?: string;
  size?: number;
  withBackground?: boolean;
}

export default function TelexLogo({
  className = "",
  size = 24,
  withBackground = true,
}: TelexLogoProps) {
  return (
    <div
      className={`inline-flex items-center justify-center select-none flex-shrink-0 ${className}`}
      style={{ width: size, height: size }}
    >
      <svg
        viewBox="0 0 100 100"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="w-full h-full"
      >
        {/* Optional Solid Black Square Background */}
        {withBackground && (
          <rect width="100" height="100" rx="16" fill="#000000" />
        )}

        {/* Crisp Bold White 'T' (Exact Proportions from User Design) */}
        {/* Top Horizontal Bar */}
        <rect x="18" y="24" width="64" height="15" fill="#FFFFFF" />
        {/* Vertical Stem */}
        <rect x="42.5" y="39" width="15" height="42" fill="#FFFFFF" />
      </svg>
    </div>
  );
}

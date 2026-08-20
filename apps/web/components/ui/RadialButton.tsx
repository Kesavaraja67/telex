"use client";

import { useState, useRef, MouseEvent, ReactNode } from "react";
import { motion, AnimatePresence } from "motion/react";

interface RadialButtonProps {
  label: string;
  colors?: {
    fill?: string;
    textColor?: string;
    hoverFill?: string;
    hoverTextColor?: string;
  };
  border?: {
    borderWidth?: number;
    borderColor?: string;
  };
  rounded?: number;
  link?: string;
  onClick?: () => void;
  className?: string;
  children?: ReactNode;
}

export default function RadialButton({
  label,
  colors = {
    fill: "#000000",
    textColor: "#F2F1ED",
    hoverFill: "#4FD1C5",
    hoverTextColor: "#000000",
  },
  border = {
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.16)",
  },
  rounded = 100,
  link,
  onClick,
  className = "",
  children,
}: RadialButtonProps) {
  const buttonRef = useRef<HTMLButtonElement | HTMLAnchorElement | null>(null);
  const [isHovered, setIsHovered] = useState(false);
  const [cursorPos, setCursorPos] = useState({ x: 0, y: 0 });

  const handleMouseMove = (e: MouseEvent<HTMLElement>) => {
    if (!buttonRef.current) return;
    const rect = buttonRef.current.getBoundingClientRect();
    setCursorPos({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    });
  };

  const handleMouseEnter = (e: MouseEvent<HTMLElement>) => {
    handleMouseMove(e);
    setIsHovered(true);
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
  };

  const fill = colors.fill ?? "#000000";
  const textColor = colors.textColor ?? "#F2F1ED";
  const hoverFill = colors.hoverFill ?? "#4FD1C5";
  const hoverTextColor = colors.hoverTextColor ?? "#000000";
  const borderWidth = border.borderWidth ?? 1;
  const borderColor = border.borderColor ?? "rgba(255, 255, 255, 0.16)";

  const content = (
    <>
      {/* Base background fill with subtle gradient */}
      <div
        className="absolute inset-0 transition-colors duration-300"
        style={{
          background: `linear-gradient(180deg, rgba(255,255,255,0.06) 0%, ${fill} 100%)`,
        }}
      />

      {/* Radial reveal effect expanding from cursor */}
      <AnimatePresence>
        {isHovered && (
          <motion.span
            className="absolute rounded-full pointer-events-none"
            initial={{ width: 0, height: 0, opacity: 0.9 }}
            animate={{ width: 340, height: 340, opacity: 1 }}
            exit={{ width: 0, height: 0, opacity: 0 }}
            transition={{ type: "spring", damping: 30, stiffness: 260 }}
            style={{
              backgroundColor: hoverFill,
              left: cursorPos.x,
              top: cursorPos.y,
              transform: "translate(-50%, -50%)",
              boxShadow: "0 0 40px rgba(79, 209, 197, 0.6)",
            }}
          />
        )}
      </AnimatePresence>

      {/* Button content */}
      <span
        className="relative z-10 font-mono text-xs sm:text-sm tracking-tight font-semibold flex items-center justify-center gap-2 transition-colors duration-200"
        style={{
          color: isHovered ? hoverTextColor : textColor,
        }}
      >
        {children || label}
      </span>
    </>
  );

  const sharedStyles = {
    borderRadius: `${rounded}px`,
    border: `${borderWidth}px solid ${isHovered ? "rgba(79, 209, 197, 0.6)" : borderColor}`,
    boxShadow: isHovered
      ? "0 0 30px rgba(79, 209, 197, 0.35), inset 0 1px 1px rgba(255,255,255,0.4)"
      : "0 10px 30px -10px rgba(0, 0, 0, 0.8), inset 0 1px 1px rgba(255,255,255,0.12)",
  };

  if (link) {
    return (
      <a
        ref={buttonRef as any}
        href={link}
        onMouseMove={handleMouseMove}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        className={`relative inline-flex items-center justify-center px-7 py-3 overflow-hidden cursor-pointer select-none transition-all duration-300 ${className}`}
        style={sharedStyles}
      >
        {content}
      </a>
    );
  }

  return (
    <button
      ref={buttonRef as any}
      onClick={onClick}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={`relative inline-flex items-center justify-center px-7 py-3 overflow-hidden cursor-pointer select-none transition-all duration-300 ${className}`}
      style={sharedStyles}
    >
      {content}
    </button>
  );
}

"use client";

import { useEffect, useRef, ButtonHTMLAttributes } from "react";
import { attachMagneticButton } from "@/lib/animations";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  magnetic?: boolean;
}

const variantStyles: Record<string, string> = {
  primary:
    "bg-patch text-ink font-semibold hover:brightness-110 shadow-[0_0_20px_rgba(79,209,197,0.3)]",
  ghost:
    "border border-muted/40 text-text hover:border-patch hover:text-patch",
  danger:
    "border border-break/40 text-break hover:bg-break/10",
};

const sizeStyles: Record<string, string> = {
  sm: "px-4 py-1.5 text-xs",
  md: "px-6 py-2.5 text-sm",
  lg: "px-8 py-3 text-base",
};

export default function Button({
  variant = "primary",
  size = "md",
  magnetic = true,
  className = "",
  children,
  ...props
}: ButtonProps) {
  const ref = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!magnetic || !ref.current) return;
    let cleanup: (() => void) | undefined;
    attachMagneticButton(ref.current).then((fn) => {
      cleanup = fn;
    });
    return () => cleanup?.();
  }, [magnetic]);

  return (
    <button
      ref={ref}
      className={[
        "font-mono tracking-tight rounded transition-all duration-200 cursor-pointer",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-patch/60",
        "disabled:opacity-40 disabled:cursor-not-allowed",
        variantStyles[variant],
        sizeStyles[size],
        className,
      ].join(" ")}
      {...props}
    >
      {children}
    </button>
  );
}

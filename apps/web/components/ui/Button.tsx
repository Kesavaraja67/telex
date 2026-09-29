"use client";

import { useEffect, useRef, ButtonHTMLAttributes } from "react";
import { attachMagneticButton } from "@/lib/animations";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "ghost" | "danger" | "key-cap";
  size?: "sm" | "md" | "lg";
  magnetic?: boolean;
}

const variantStyles: Record<string, string> = {
  primary: "key-cap",
  ghost: "key-cap key-cap--ghost",
  danger: "key-cap border-rose-950/80 text-rose-300 hover:text-white shadow-[0_2px_0_#1a080c,0_3px_0_#100508,0_4px_10px_rgba(244,63,94,0.15)]",
  "key-cap": "key-cap",
};

const sizeStyles: Record<string, string> = {
  sm: "key-cap--sm",
  md: "px-5 py-2 text-xs sm:text-sm",
  lg: "key-cap--lg",
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
        "font-mono tracking-wider inline-flex items-center justify-center gap-2 select-none",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40",
        variantStyles[variant] || "key-cap",
        sizeStyles[size] || "",
        className,
      ].join(" ")}
      {...props}
    >
      {children}
    </button>
  );
}


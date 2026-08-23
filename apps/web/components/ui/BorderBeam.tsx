"use client";

import React from "react";

interface BorderBeamProps {
  size?: number;
  duration?: number;
  anchor?: number;
  borderWidth?: number;
  colorFrom?: string;
  colorTo?: string;
  delay?: number;
  className?: string;
}

export default function BorderBeam({
  size = 220,
  duration = 10,
  anchor = 90,
  borderWidth = 1.5,
  colorFrom = "#FFFFFF",
  colorTo = "rgba(255, 255, 255, 0.1)",
  delay = 0,
  className = "",
}: BorderBeamProps) {
  return (
    <div
      style={
        {
          "--size": size,
          "--duration": duration,
          "--anchor": anchor,
          "--border-width": borderWidth,
          "--color-from": colorFrom,
          "--color-to": colorTo,
          "--delay": `-${delay}s`,
        } as React.CSSProperties
      }
      className={`pointer-events-none absolute inset-0 rounded-[inherit] [border:calc(var(--border-width)*1px)_solid_transparent] ![mask-clip:padding-box,border-box] ![mask-composite:intersect] [mask:linear-gradient(transparent,transparent),linear-gradient(white,white)] after:absolute after:aspect-square after:w-[calc(var(--size)*1px)] after:animate-[border-beam_calc(var(--duration)*1s)_infinite_linear] after:[animation-delay:var(--delay)] after:[background:linear-gradient(to_left,var(--color-from),var(--color-to),transparent)] after:[offset-anchor:calc(var(--anchor)*1%)_50%] after:[offset-path:rect(0_auto_auto_0_round_calc(var(--size)*1px))] ${className}`}
    />
  );
}

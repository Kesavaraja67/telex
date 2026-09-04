"use client";

import { useState, useEffect } from "react";

interface WordProps {
  original: string;
  className?: string;
}

const GLYPHS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789//";

function ScrambleWord({ original, className = "" }: WordProps) {
  const [displayText, setDisplayText] = useState(original);
  const [isHovered, setIsHovered] = useState(false);

  useEffect(() => {
    if (!isHovered) {
      setDisplayText(original);
      return;
    }

    let iteration = 0;
    const interval = setInterval(() => {
      setDisplayText(() =>
        original
          .split("")
          .map((char, index) => {
            if (char === " " || char === "." || char === "-" || char === ",") return char;
            if (index < iteration) {
              return original[index];
            }
            return GLYPHS[Math.floor(Math.random() * GLYPHS.length)];
          })
          .join("")
      );

      if (iteration >= original.length) {
        clearInterval(interval);
      }

      iteration += 1 / 2;
    }, 30);

    return () => clearInterval(interval);
  }, [isHovered, original]);

  return (
    <span
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className={`inline-block cursor-pointer transition-all duration-300 select-none ${
        isHovered
          ? "text-white drop-shadow-[0_0_20px_rgba(255,255,255,0.6)]"
          : "hover:text-[#ECE7DA]"
      } ${className}`}
    >
      {displayText}
    </span>
  );
}

export default function InteractiveHeadline() {
  return (
    <h1
      className="font-display font-extrabold leading-[0.95] text-white tracking-[-0.04em] uppercase my-3"
      style={{
        fontSize: "clamp(2.5rem, 7vw, 5.2rem)",
      }}
    >
      <ScrambleWord original="RAZORPAY" className="mr-3 sm:mr-4" />
      <ScrambleWord original="PAYMENTS" />
      <br />
      <span className="text-[#ECE7DA]">
        <ScrambleWord original="JUST" className="mr-3 sm:mr-4" />
        <ScrambleWord original="HEALED" className="mr-3 sm:mr-4" />
        <ScrambleWord original="THEMSELVES." />
      </span>
    </h1>
  );
}

"use client";

import { useEffect, useState } from "react";

export default function Marginalia() {
  const [coords, setCoords] = useState({ x: 0, y: 0 });
  const [mousePos, setMousePos] = useState({ x: -1000, y: -1000 });

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      const normX = (e.clientX / window.innerWidth) * 100;
      const normY = (e.clientY / window.innerHeight) * 100;
      setCoords({
        x: parseFloat(normX.toFixed(2)),
        y: parseFloat(normY.toFixed(2)),
      });
      setMousePos({ x: e.clientX, y: e.clientY });
    };

    window.addEventListener("mousemove", handleMouseMove, { passive: true });
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);

  return (
    <>
      {/* Interactive Cursor Spotlight Glow */}
      <div
        className="pointer-events-none fixed inset-0 z-30 transition-opacity duration-300 opacity-50"
        style={{
          background: `radial-gradient(600px circle at ${mousePos.x}px ${mousePos.y}px, rgba(255, 255, 255, 0.035), transparent 40%)`,
        }}
      />

      {/* Fixed Marginalia Coordinates on bottom left */}
      <div className="fixed bottom-6 left-6 z-40 hidden md:flex items-center gap-3 font-mono text-[10px] tracking-[0.25em] text-[#888888] select-none bg-black/60 backdrop-blur-2xl px-4 py-2 rounded-full border border-white/10 shadow-lg">
        <span className="w-1.5 h-1.5 rounded-full bg-white animate-ping" />
        <span>
          X: {coords.x < 10 ? `0${coords.x}` : coords.x}
        </span>
        <span className="text-white/20">|</span>
        <span>
          Y: {coords.y < 10 ? `0${coords.y}` : coords.y}
        </span>
      </div>
    </>
  );
}

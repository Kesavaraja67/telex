"use client";

import React from "react";
import { motion } from "motion/react";

interface KineticHeaderProps {
  title: string;
  subtitle?: string;
  badge?: string;
  className?: string;
}

export default function KineticHeader({
  title,
  subtitle,
  badge,
  className = "",
}: KineticHeaderProps) {
  const words = title.split(" ");

  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      {badge && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9, y: 5 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="self-start"
        >
          <span className="font-mono text-[10px] uppercase tracking-widest px-2.5 py-1 rounded-full bg-white/10 text-white border border-white/20">
            {badge}
          </span>
        </motion.div>
      )}

      <div className="overflow-hidden flex flex-wrap gap-x-3">
        {words.map((word, idx) => (
          <motion.h1
            key={idx}
            initial={{ y: "100%", opacity: 0 }}
            animate={{ y: "0%", opacity: 1 }}
            transition={{
              duration: 0.5,
              delay: idx * 0.08,
              ease: [0.215, 0.61, 0.355, 1], // Cubic bezier ease-out
            }}
            className="font-mono font-bold text-2xl md:text-3xl text-white tracking-tight inline-block"
          >
            {word}
          </motion.h1>
        ))}
      </div>

      {subtitle && (
        <motion.p
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.25 }}
          className="font-sans text-sm text-[#A1A1AA] max-w-2xl leading-relaxed"
        >
          {subtitle}
        </motion.p>
      )}
    </div>
  );
}

"use client";

import React from "react";
import { motion } from "motion/react";

export default function CyberGridBackground() {
  return (
    <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
      {/* Cyber Grid Layer */}
      <div className="absolute inset-0 cyber-grid cyber-grid-radial-mask opacity-60" />

      {/* Pure White Ambient Organic Light Mesh */}
      <motion.div
        animate={{
          x: [0, 30, -25, 0],
          y: [0, -25, 30, 0],
          scale: [1, 1.1, 0.95, 1],
          opacity: [0.04, 0.08, 0.05, 0.04],
        }}
        transition={{
          duration: 18,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        className="absolute -top-32 -left-32 w-[600px] h-[600px] rounded-full bg-white blur-[160px]"
      />

      <motion.div
        animate={{
          x: [0, -40, 25, 0],
          y: [0, 35, -25, 0],
          scale: [1, 1.08, 0.92, 1],
          opacity: [0.03, 0.06, 0.04, 0.03],
        }}
        transition={{
          duration: 22,
          repeat: Infinity,
          ease: "easeInOut",
          delay: 2,
        }}
        className="absolute top-1/3 -right-32 w-[550px] h-[550px] rounded-full bg-white blur-[170px]"
      />
    </div>
  );
}

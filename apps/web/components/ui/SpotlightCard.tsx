"use client";

import React, { useRef, useState, useCallback } from "react";
import { motion, type HTMLMotionProps } from "motion/react";

interface SpotlightCardProps extends HTMLMotionProps<"div"> {
  children: React.ReactNode;
  spotlightColor?: string;
  className?: string;
  enableTilt?: boolean;
}

export default function SpotlightCard({
  children,
  spotlightColor = "rgba(255, 255, 255, 0.1)",
  className = "",
  enableTilt = true,
  ...props
}: SpotlightCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0, opacity: 0 });
  const [rotate, setRotate] = useState({ x: 0, y: 0 });

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!cardRef.current) return;
      const rect = cardRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      setMousePos({ x, y, opacity: 1 });

      if (enableTilt) {
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        const rotateX = ((y - centerY) / centerY) * -3; // Subtle 3 deg tilt
        const rotateY = ((x - centerX) / centerX) * 3;
        setRotate({ x: rotateX, y: rotateY });
      }
    },
    [enableTilt]
  );

  const handleMouseLeave = useCallback(() => {
    setMousePos((prev) => ({ ...prev, opacity: 0 }));
    setRotate({ x: 0, y: 0 });
  }, []);

  return (
    <motion.div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      animate={{
        rotateX: rotate.x,
        rotateY: rotate.y,
      }}
      transition={{ type: "spring", stiffness: 350, damping: 25 }}
      style={{
        transformStyle: "preserve-3d",
      }}
      className={`glass-surface relative overflow-hidden rounded-2xl ${className}`}
      {...props}
    >
      {/* Dynamic Pure White Radial Cursor Spotlight */}
      <div
        className="pointer-events-none absolute -inset-px transition-opacity duration-300 rounded-[inherit]"
        style={{
          opacity: mousePos.opacity,
          background: `radial-gradient(450px circle at ${mousePos.x}px ${mousePos.y}px, ${spotlightColor}, transparent 65%)`,
        }}
      />
      {children}
    </motion.div>
  );
}

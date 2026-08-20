"use client";

import { useEffect, useRef } from "react";

interface StarFieldProps {
  color1?: string;
  color2?: string;
  color3?: string;
  particleCount?: number;
  speed?: number;
  glitterIntensity?: number;
  brightness?: number;
  className?: string;
}

export default function StarField({
  color1 = "#ffffff",
  color2 = "#8B9099",
  color3 = "#444444",
  particleCount = 90,
  speed = 1.0,
  glitterIntensity = 1.4,
  brightness = 45,
  className = "",
}: StarFieldProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let width = 0;
    let height = 0;
    let dpr = 1;

    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = canvas.parentElement?.clientWidth || window.innerWidth;
      height = canvas.parentElement?.clientHeight || 600;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx.scale(dpr, dpr);
    };

    resize();

    const colors = [color1, color2, color3];

    interface Particle {
      x: number;
      y: number;
      size: number;
      color: string;
      vx: number;
      vy: number;
      baseAlpha: number;
      alpha: number;
      pulseSpeed: number;
      phase: number;
    }

    const particles: Particle[] = Array.from({ length: particleCount }, () => {
      const color = colors[Math.floor(Math.random() * colors.length)];
      const baseAlpha = (Math.random() * 0.4 + 0.1) * (brightness / 100);
      return {
        x: Math.random() * width,
        y: Math.random() * height,
        size: Math.random() * 1.5 + 0.5,
        color,
        vx: (Math.random() - 0.5) * 0.2 * speed,
        vy: (Math.random() - 0.5) * 0.2 * speed,
        baseAlpha,
        alpha: baseAlpha,
        pulseSpeed: (Math.random() * 0.03 + 0.01) * glitterIntensity,
        phase: Math.random() * Math.PI * 2,
      };
    });

    let frameId: number;
    let time = 0;

    const render = () => {
      frameId = requestAnimationFrame(render);
      time += 0.02;

      ctx.clearRect(0, 0, width, height);

      for (const p of particles) {
        p.x += p.vx;
        p.y += p.vy;

        if (p.x < 0) p.x = width;
        if (p.x > width) p.x = 0;
        if (p.y < 0) p.y = height;
        if (p.y > height) p.y = 0;

        p.alpha =
          p.baseAlpha +
          Math.sin(time * p.pulseSpeed * 40 + p.phase) *
            0.15 *
            glitterIntensity;
        p.alpha = Math.max(0.04, Math.min(0.85, p.alpha));

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = p.color;
        ctx.globalAlpha = p.alpha;
        ctx.fill();
      }

      ctx.globalAlpha = 1.0;
    };

    render();
    window.addEventListener("resize", resize);

    return () => {
      cancelAnimationFrame(frameId);
      window.removeEventListener("resize", resize);
    };
  }, [color1, color2, color3, particleCount, speed, glitterIntensity, brightness]);

  return (
    <canvas
      ref={canvasRef}
      className={`absolute inset-0 w-full h-full pointer-events-none ${className}`}
      style={{ display: "block" }}
    />
  );
}

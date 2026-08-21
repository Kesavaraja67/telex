"use client";

/**
 * Shared animation factories — Section 8.4.
 * Uses animejs v4 API (animate / stagger / createTimeline).
 * All animations respect prefers-reduced-motion.
 */

/** True if the user prefers reduced motion. */
export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * 1. Ticket print-in — staggered translateY + opacity.
 * Used by TicketFeed when new cards enter the DOM.
 */
export async function animateTicketIn(targets: NodeListOf<Element> | Element[]) {
  if (prefersReducedMotion()) {
    // Instant show for reduced motion
    Array.from(targets).forEach((el) => {
      (el as HTMLElement).style.opacity = "1";
      (el as HTMLElement).style.transform = "translateY(0)";
    });
    return;
  }
  const { animate, stagger } = await import("animejs");
  animate(Array.from(targets), {
    translateY: [-24, 0],
    opacity: [0, 1],
    duration: 420,
    ease: "outExpo",
    delay: stagger(60),
  });
}

/**
 * 2. Diff typing reveal — character-by-character opacity.
 * Wrap each character in a <span class="char"> before calling this.
 */
export async function animateDiffReveal(targets: NodeListOf<Element> | Element[]) {
  if (prefersReducedMotion()) {
    Array.from(targets).forEach((el) => {
      (el as HTMLElement).style.opacity = "1";
    });
    return;
  }
  const { animate, stagger } = await import("animejs");
  animate(Array.from(targets), {
    opacity: [0, 1],
    duration: 1,
    ease: "steps(1)",
    delay: stagger(14),
  });
}

/**
 * 3. Stat count-up — animates a numeric value on an element.
 */
export async function animateCountUp(
  element: HTMLElement,
  targetValue: number,
  suffix = ""
) {
  if (prefersReducedMotion()) {
    element.textContent = String(targetValue) + suffix;
    return;
  }
  const { animate } = await import("animejs");
  const obj = { val: 0 };
  animate(obj, {
    val: targetValue,
    duration: 1400,
    ease: "outCubic",
    onUpdate: () => {
      element.textContent = String(Math.round(obj.val)) + suffix;
    },
  });
}

/**
 * 4. Magnetic CTA button — tracks cursor, springs back on leave.
 */
export async function attachMagneticButton(button: HTMLElement) {
  if (prefersReducedMotion()) return () => {};
  const { animate } = await import("animejs");

  function onMouseMove(e: MouseEvent) {
    const r = button.getBoundingClientRect();
    animate(button, {
      translateX: (e.clientX - r.left - r.width / 2) * 0.2,
      translateY: (e.clientY - r.top - r.height / 2) * 0.3,
      duration: 300,
      ease: "outQuad",
    });
  }

  function onMouseLeave() {
    animate(button, {
      translateX: 0,
      translateY: 0,
      duration: 400,
      ease: "outElastic(1, .6)",
    });
  }

  button.addEventListener("mousemove", onMouseMove);
  button.addEventListener("mouseleave", onMouseLeave);

  return () => {
    button.removeEventListener("mousemove", onMouseMove);
    button.removeEventListener("mouseleave", onMouseLeave);
  };
}

/**
 * Generic fade-in-up for sections entering the viewport.
 */
export async function animateFadeInUp(targets: Element | Element[], delay = 0) {
  if (prefersReducedMotion()) return;
  const { animate } = await import("animejs");
  animate(Array.isArray(targets) ? targets : [targets], {
    translateY: [32, 0],
    opacity: [0, 1],
    duration: 600,
    ease: "outExpo",
    delay,
  });
}

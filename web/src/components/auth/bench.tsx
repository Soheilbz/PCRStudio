import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * The auth section's instrument chrome: a measurement strip, a label voice,
 * and the helix. Each earns its place once per screen and no louder.
 */

/**
 * A measurement strip with major and minor ticks, like any real ruler: fine
 * marks every 8px, a taller mark every 48px. Two overlaid gradients so the
 * major ticks read as such rather than as noise.
 */
export function TickRule({ className }: { className?: string }) {
  return (
    <div aria-hidden="true" className={cn("relative h-2.5 select-none", className)}>
      <div
        className="absolute inset-x-0 bottom-0 h-1.5"
        style={{
          backgroundImage:
            "repeating-linear-gradient(to right, var(--border) 0 1px, transparent 1px 8px)",
        }}
      />
      <div
        className="absolute inset-x-0 bottom-0 h-2.5"
        style={{
          backgroundImage:
            "repeating-linear-gradient(to right, var(--border) 0 1px, transparent 1px 48px)",
        }}
      />
      <div className="absolute inset-x-0 bottom-0 h-px bg-border" />
    </div>
  );
}

/** Small-caps mono metadata line — the instrument's voice for labels. */
export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p
      className={cn(
        // `primary`, not `brand`: the lighter brand amber misses 4.5:1 on the
        // light card at this size. Same hue family, AA-passing in both themes.
        "font-mono text-xs font-medium tracking-[0.16em] text-primary uppercase",
        className,
      )}
    >
      {children}
    </p>
  );
}

/**
 * A hairline double helix, drifting slowly upward behind the protocol sheet.
 *
 * Drawn from the same geometry a sequence diagram would use - two sine
 * strands, base-pair rungs whose length follows the strand separation - so it
 * reads as domain artifact rather than ornament. Three periods are drawn and
 * the group slides exactly one period before looping, which makes the drift
 * seamless; reduced-motion readers get the still helix.
 */
export function HelixDrift({ className }: { className?: string }) {
  const PERIOD = 96;
  const AMPLITUDE = 21;
  const MID = 32;
  const STEPS = 64;
  const RUNGS = 36;

  const strand = (phase: number) => {
    const points: string[] = [];
    for (let i = 0; i <= STEPS; i++) {
      const y = (i / STEPS) * PERIOD * 3;
      const x = MID + AMPLITUDE * Math.sin((2 * Math.PI * y) / PERIOD + phase);
      points.push(`${x.toFixed(1)},${y.toFixed(1)}`);
    }
    return points.join(" ");
  };

  const rungs: { x1: number; x2: number; y: number; strength: number; opacity: number }[] = [];
  for (let i = 0; i < RUNGS; i++) {
    const y = (i / RUNGS) * PERIOD * 3;
    const a = MID + AMPLITUDE * Math.sin((2 * Math.PI * y) / PERIOD);
    const b = MID + AMPLITUDE * Math.sin((2 * Math.PI * y) / PERIOD + Math.PI);
    const x1 = Math.min(a, b);
    const x2 = Math.max(a, b);
    const strength = Math.abs(Math.sin((2 * Math.PI * y) / PERIOD));
    const opacity = 0.35 + 0.45 * strength;
    rungs.push({
      x1: Number(x1.toFixed(1)),
      x2: Number(x2.toFixed(1)),
      y: Number(y.toFixed(1)),
      strength: Number(strength.toFixed(4)),
      opacity: Number(opacity.toFixed(4)),
    });
  }

  return (
    <div aria-hidden="true" className={cn("pointer-events-none overflow-hidden", className)}>
      <svg
        viewBox={`0 0 64 ${PERIOD * 3}`}
        preserveAspectRatio="xMidYMin slice"
        className="h-[calc(100%+96px)] w-full [animation:helix-drift_36s_linear_infinite] motion-reduce:[animation:none]"
      >
        {rungs.map((rung, index) => (
          <line
            key={index}
            x1={rung.x1}
            x2={rung.x2}
            y1={rung.y}
            y2={rung.y}
            stroke="var(--border)"
            strokeWidth={1}
            opacity={rung.opacity}
          />
        ))}
        <polyline
          points={strand(0)}
          fill="none"
          stroke="var(--brand-muted)"
          strokeWidth={1.25}
          opacity={0.55}
        />
        <polyline
          points={strand(Math.PI)}
          fill="none"
          stroke="var(--brand-muted)"
          strokeWidth={1.25}
          opacity={0.55}
        />
      </svg>
    </div>
  );
}

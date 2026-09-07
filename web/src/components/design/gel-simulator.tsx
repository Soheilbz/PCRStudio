"use client";

import { useMemo, useState } from "react";
import { count } from "@/lib/numbers";
import { cn } from "@/lib/utils";

export interface GelBand {
  label: string;
  size: number;
  intensity?: number; // 1 = standard, 2 = bright reference, 0.5 = faint
  isOffTarget?: boolean;
}

export interface GelSimulatorProps {
  products: GelBand[];
  className?: string;
}

const LADDER_100BP = [
  { size: 2000, label: "2.0 kb", intensity: 1 },
  { size: 1500, label: "1.5 kb", intensity: 1 },
  { size: 1000, label: "1.0 kb", intensity: 1 },
  { size: 900, label: "900", intensity: 1 },
  { size: 800, label: "800", intensity: 1 },
  { size: 700, label: "700", intensity: 1 },
  { size: 600, label: "600", intensity: 1 },
  { size: 500, label: "500", intensity: 2.2 }, // Reference bright band
  { size: 400, label: "400", intensity: 1 },
  { size: 300, label: "300", intensity: 1 },
  { size: 200, label: "200", intensity: 1 },
  { size: 100, label: "100", intensity: 1 },
];

const LADDER_1KB = [
  { size: 10000, label: "10.0 kb", intensity: 1 },
  { size: 8000, label: "8.0 kb", intensity: 1 },
  { size: 6000, label: "6.0 kb", intensity: 1 },
  { size: 5000, label: "5.0 kb", intensity: 1 },
  { size: 4000, label: "4.0 kb", intensity: 1 },
  { size: 3000, label: "3.0 kb", intensity: 2.2 }, // Reference bright band
  { size: 2000, label: "2.0 kb", intensity: 1 },
  { size: 1500, label: "1.5 kb", intensity: 1 },
  { size: 1000, label: "1.0 kb", intensity: 1 },
  { size: 500, label: "500 bp", intensity: 1 },
];

/**
 * Virtual Agarose Gel Electrophoresis Migration Simulator.
 * Accurately maps DNA fragment migration distance proportionally to -log10(size).
 */
export function GelSimulator({ products, className }: GelSimulatorProps) {
  const [ladderType, setLadderType] = useState<"100bp" | "1kb">(() => {
    const maxProduct = Math.max(...products.map((p) => p.size), 300);
    return maxProduct > 1600 ? "1kb" : "100bp";
  });
  const [gelPercent, setGelPercent] = useState<"1.0" | "1.5" | "2.0">("1.5");
  const [hoveredBand, setHoveredBand] = useState<string | null>(null);

  const ladder = ladderType === "100bp" ? LADDER_100BP : LADDER_1KB;
  const minSize = ladderType === "100bp" ? 80 : 350;
  const maxSize = ladderType === "100bp" ? 2400 : 12000;

  const minLog = Math.log10(minSize);
  const maxLog = Math.log10(maxSize);

  // Height & Geometry
  const gelHeight = 280;
  const topWellY = 28;
  const migrationAreaHeight = gelHeight - topWellY - 24;

  const calculateY = (size: number) => {
    const clamped = Math.max(minSize, Math.min(maxSize, size));
    const logSize = Math.log10(clamped);
    // Relative mobility: smaller DNA migrates further (lower in gel / higher Y)
    const mobility = (maxLog - logSize) / (maxLog - minLog);
    return topWellY + 10 + mobility * migrationAreaHeight;
  };

  const validProducts = useMemo(
    () => products.filter((p) => Number.isFinite(p.size) && p.size > 0),
    [products],
  );

  return (
    <div
      className={cn(
        "workbench-card space-y-3 rounded-lg border bg-surface-wash/45 p-3.5",
        className,
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b pb-2.5">
        <div className="space-y-0.5">
          <span className="text-xs font-semibold text-foreground">Agarose Gel Simulation</span>
          <p className="text-xs text-muted-foreground">
            Predicted electrophoretic mobility against reference DNA ladder
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          <div
            className="flex items-center gap-1 rounded-md border bg-muted/30 p-0.5"
            role="group"
            aria-label="DNA ladder"
          >
            <button
              type="button"
              aria-pressed={ladderType === "100bp"}
              onClick={() => setLadderType("100bp")}
              className={cn(
                "min-h-6 rounded px-2 py-0.5 text-xs font-medium transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                ladderType === "100bp"
                  ? "bg-surface-wash/55 text-foreground shadow-xs"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              100 bp Ladder
            </button>
            <button
              type="button"
              aria-pressed={ladderType === "1kb"}
              onClick={() => setLadderType("1kb")}
              className={cn(
                "min-h-6 rounded px-2 py-0.5 text-xs font-medium transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                ladderType === "1kb"
                  ? "bg-surface-wash/55 text-foreground shadow-xs"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              1 kb Ladder
            </button>
          </div>

          <div
            className="flex items-center gap-1 rounded-md border bg-muted/30 p-0.5 text-xs"
            role="group"
            aria-label="Gel concentration"
          >
            <span className="px-1.5 text-muted-foreground">Gel:</span>
            {(["1.0", "1.5", "2.0"] as const).map((pct) => (
              <button
                key={pct}
                type="button"
                aria-pressed={gelPercent === pct}
                onClick={() => setGelPercent(pct)}
                className={cn(
                  "min-h-6 rounded px-1.5 py-0.5 font-medium transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                  gelPercent === pct
                    ? "bg-surface-wash/55 text-foreground shadow-xs"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {pct}%
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Gel Transilluminator Tank */}
      <div className="relative mx-auto flex max-w-lg justify-center overflow-hidden rounded-md border border-neutral-800 bg-[#0c1017] p-4 text-xs shadow-inner select-none">
        {/* Glow backdrop */}
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-blue-950/20 via-transparent to-transparent" />

        <svg
          viewBox="0 0 380 280"
          className="h-[280px] w-full max-w-[380px]"
          role="img"
          aria-label="Simulated Agarose Gel Electrophoresis Tank"
        >
          {/* Well Comb Loading Wells */}
          {/* Lane 1: Ladder Well */}
          <rect
            x="70"
            y="12"
            width="36"
            height="10"
            rx="1.5"
            className="fill-neutral-900 stroke-neutral-700"
            strokeWidth="1"
          />
          <text x="88" y="9" textAnchor="middle" className="fill-neutral-400 font-mono text-[10px]">
            LADDER
          </text>

          {/* Lane 2: Target Reaction Product Well */}
          <rect
            x="180"
            y="12"
            width="44"
            height="10"
            rx="1.5"
            className="fill-neutral-900 stroke-neutral-700"
            strokeWidth="1"
          />
          <text
            x="202"
            y="9"
            textAnchor="middle"
            className="fill-neutral-400 font-mono text-[10px]"
          >
            PRODUCT
          </text>

          {/* Lane 3: Off-target check well if present */}
          {validProducts.some((p) => p.isOffTarget) ? (
            <>
              <rect
                x="290"
                y="12"
                width="40"
                height="10"
                rx="1.5"
                className="fill-neutral-900 stroke-neutral-700"
                strokeWidth="1"
              />
              <text
                x="310"
                y="9"
                textAnchor="middle"
                className="fill-neutral-400 font-mono text-[10px]"
              >
                OFF-TARGETS
              </text>
            </>
          ) : null}

          {/* Lane 1: Ladder Bands */}
          {ladder.map((band) => {
            const y = calculateY(band.size);
            const isBright = band.intensity > 1.5;
            return (
              <g
                key={band.size}
                className="transition-opacity hover:opacity-100"
                onMouseEnter={() =>
                  setHoveredBand(`Ladder Standard: ${band.label} (${count(band.size)} bp)`)
                }
                onMouseLeave={() => setHoveredBand(null)}
              >
                {/* Band glow & core */}
                <rect
                  x="72"
                  y={y - (isBright ? 2 : 1.5)}
                  width="32"
                  height={isBright ? 4 : 2.5}
                  rx="1"
                  className={cn(
                    isBright
                      ? "fill-cyan-200 drop-shadow-[0_0_6px_rgba(34,211,238,0.9)]"
                      : "fill-cyan-300/80 drop-shadow-[0_0_3px_rgba(34,211,238,0.5)]",
                  )}
                />
                {/* Size label on left */}
                <text
                  x="62"
                  y={y + 3}
                  textAnchor="end"
                  className={cn(
                    "font-mono text-[10px] tabular-nums",
                    isBright ? "fill-cyan-300 font-semibold" : "fill-neutral-400",
                  )}
                >
                  {band.label}
                </text>
              </g>
            );
          })}

          {/* Lane 2: Main Amplicon Product Bands */}
          {validProducts
            .filter((p) => !p.isOffTarget)
            .map((prod, idx) => {
              const y = calculateY(prod.size);
              return (
                <g
                  key={`${prod.label}-${prod.size}-${idx}`}
                  className="cursor-pointer"
                  onMouseEnter={() =>
                    setHoveredBand(`Target Amplicon: ${prod.label} (${count(prod.size)} bp)`)
                  }
                  onMouseLeave={() => setHoveredBand(null)}
                >
                  {/* Outer diffuse glow */}
                  <rect
                    x="178"
                    y={y - 3}
                    width="48"
                    height="7"
                    rx="2"
                    className="fill-amber-400/40 blur-[2px]"
                  />
                  {/* Sharp core band */}
                  <rect
                    x="180"
                    y={y - 1.5}
                    width="44"
                    height="3.5"
                    rx="1"
                    className="fill-amber-200 drop-shadow-[0_0_8px_rgba(251,191,36,0.95)]"
                  />
                  {/* Size label beside band */}
                  <text
                    x="232"
                    y={y + 3}
                    textAnchor="start"
                    className="fill-amber-300 font-mono text-[10px] font-semibold tabular-nums drop-shadow-[0_0_3px_rgba(0,0,0,0.8)]"
                  >
                    {prod.size} bp
                  </text>
                </g>
              );
            })}

          {/* Lane 3: Off-target bands if present */}
          {validProducts
            .filter((p) => p.isOffTarget)
            .map((prod, idx) => {
              const y = calculateY(prod.size);
              return (
                <g
                  key={`off-${prod.size}-${idx}`}
                  className="cursor-pointer"
                  onMouseEnter={() =>
                    setHoveredBand(`Predicted Off-target: ${prod.label} (${count(prod.size)} bp)`)
                  }
                  onMouseLeave={() => setHoveredBand(null)}
                >
                  <rect
                    x="292"
                    y={y - 1}
                    width="36"
                    height="2.5"
                    rx="1"
                    className="fill-rose-300/80 drop-shadow-[0_0_5px_rgba(244,63,94,0.7)]"
                  />
                  <text
                    x="334"
                    y={y + 3}
                    textAnchor="start"
                    className="fill-rose-400 font-mono text-[10px] tabular-nums"
                  >
                    {prod.size} bp
                  </text>
                </g>
              );
            })}
        </svg>
      </div>

      {/* Status & Inspection bar */}
      <div className="flex min-h-5 items-center justify-between rounded bg-muted/40 px-2.5 py-1 text-xs">
        <span className="font-mono text-xs text-muted-foreground">
          {hoveredBand ??
            `${validProducts.length} product band(s) modeled on ${gelPercent}% agarose gel.`}
        </span>
        <span className="text-xs text-muted-foreground">Logarithmic migration</span>
      </div>
    </div>
  );
}

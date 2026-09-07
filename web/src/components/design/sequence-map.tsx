"use client";

import { useId, useState } from "react";
import { count } from "@/lib/numbers";
import { cn } from "@/lib/utils";
import type { PrimerPair } from "@/lib/api/types";

export interface SequenceMapProps {
  templateLength: number;
  templateName?: string;
  pair: PrimerPair;
  probe?: {
    sequence: string;
    start: number;
    length: number;
    tm?: number;
  } | null;
  avoidedRegions?: Array<{ from: number; to: number }>;
  className?: string;
}

/**
 * Interactive SVG visualization of primer binding sites, probe, and product span
 * along the template coordinate frame.
 */
export function SequenceMap({
  templateLength,
  templateName,
  pair,
  probe,
  avoidedRegions = [],
  className,
}: SequenceMapProps) {
  const mapId = useId();
  const [hoveredItem, setHoveredItem] = useState<{
    label: string;
    details: string;
    coords: string;
  } | null>(null);

  if (!templateLength || templateLength <= 0) return null;

  // Viewbox coordinates
  const svgWidth = 800;
  const svgHeight = 160;
  const paddingX = 40;
  const trackWidth = svgWidth - paddingX * 2;
  const trackY = 85;

  const toX = (baseIndex1Based: number) => {
    const fraction = Math.max(0, Math.min(1, (baseIndex1Based - 1) / (templateLength - 1 || 1)));
    return paddingX + fraction * trackWidth;
  };

  // Left primer coordinates
  const leftStart = pair.left_at.start + 1;
  const leftEnd = pair.left_at.start + pair.left_at.length;
  const leftX1 = toX(leftStart);
  const leftX2 = toX(leftEnd);

  // Right primer coordinates (Primer3 reports 3' end in 0-based indexing)
  const rightStart = pair.right_at.start - pair.right_at.length + 2;
  const rightEnd = pair.right_at.start + 1;
  const rightX1 = toX(rightStart);
  const rightX2 = toX(rightEnd);

  // Product amplicon span
  const ampliconX1 = Math.min(leftX1, rightX1);
  const ampliconX2 = Math.max(leftX2, rightX2);
  const ampliconWidth = Math.max(4, ampliconX2 - ampliconX1);

  // Probe coordinates if present
  const probeX1 = probe ? toX(probe.start) : 0;
  const probeX2 = probe ? toX(probe.start + probe.length - 1) : 0;
  const probeWidth = Math.max(4, probeX2 - probeX1);

  // Step ticks for coordinate axis
  const tickSteps = [
    1,
    Math.round(templateLength * 0.25),
    Math.round(templateLength * 0.5),
    Math.round(templateLength * 0.75),
    templateLength,
  ];
  const uniqueTicks = Array.from(new Set(tickSteps)).sort((a, b) => a - b);

  return (
    <div
      className={cn(
        "workbench-card space-y-2 rounded-lg border bg-surface-wash/45 p-3.5",
        className,
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-foreground">Binding Map</span>
          <span className="text-xs text-muted-foreground">
            {templateName ? `${templateName} — ` : ""}
            {count(templateLength)} bp
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <span className="size-2 rounded-full bg-primary" /> Forward (5′→3′)
          </span>
          <span className="flex items-center gap-1">
            <span className="size-2 rounded-full bg-chart-4" /> Reverse (5′→3′)
          </span>
          {probe ? (
            <span className="flex items-center gap-1">
              <span className="size-2 rounded-full bg-chart-5" /> Probe
            </span>
          ) : null}
          <span className="flex items-center gap-1">
            <span className="h-1.5 w-3 rounded bg-primary/20 ring-1 ring-primary/40" /> Amplicon (
            {pair.product_size} bp)
          </span>
        </div>
      </div>

      <div className="relative overflow-x-auto">
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="w-full min-w-[500px] text-xs select-none"
          role="img"
          aria-label={`Binding map showing forward primer at ${leftStart} to ${leftEnd}, reverse primer at ${rightStart} to ${rightEnd}, and product of ${pair.product_size} basepairs.`}
        >
          <defs>
            {/* Arrow markers */}
            <marker
              id={`${mapId}-arrow-fwd`}
              viewBox="0 0 10 10"
              refX="6"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 10 5 L 0 9 z" className="fill-primary" />
            </marker>
            <marker
              id={`${mapId}-arrow-rev`}
              viewBox="0 0 10 10"
              refX="6"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 10 1 L 0 5 L 10 9 z" className="fill-chart-4" />
            </marker>
          </defs>

          {/* Coordinate grid & background track */}
          <line
            x1={paddingX}
            y1={trackY}
            x2={paddingX + trackWidth}
            y2={trackY}
            className="stroke-muted-foreground/30"
            strokeWidth="4"
            strokeLinecap="round"
          />

          {/* Avoided / Excluded regions */}
          {avoidedRegions.map((region, idx) => {
            const rx1 = toX(region.from);
            const rx2 = toX(region.to);
            const rWidth = Math.max(2, rx2 - rx1);
            return (
              <rect
                key={idx}
                x={rx1}
                y={trackY - 14}
                width={rWidth}
                height={28}
                className="fill-destructive/15 stroke-destructive/40"
                strokeWidth="1"
                strokeDasharray="2,2"
                rx="2"
                onMouseEnter={() =>
                  setHoveredItem({
                    label: "Excluded Region",
                    details: `No primer allowed`,
                    coords: `${count(region.from)}–${count(region.to)} bp`,
                  })
                }
                onMouseLeave={() => setHoveredItem(null)}
              />
            );
          })}

          {/* Amplicon product highlight spanning between primers */}
          <rect
            x={ampliconX1}
            y={trackY - 8}
            width={ampliconWidth}
            height={16}
            rx="3"
            className="fill-primary/15 stroke-primary/40 transition-colors"
            strokeWidth="1"
            onMouseEnter={() =>
              setHoveredItem({
                label: "Amplicon Product",
                details: `${pair.product_size} bp product`,
                coords: `${count(leftStart)}–${count(rightEnd)} bp`,
              })
            }
            onMouseLeave={() => setHoveredItem(null)}
          />

          {/* Forward primer (Left, 5' -> 3' pointing Right) */}
          <g
            className="cursor-pointer transition-opacity hover:opacity-90"
            onMouseEnter={() =>
              setHoveredItem({
                label: "Forward Primer",
                details: `${pair.left.length} nt · ${pair.left.gc_percent}% GC · ${pair.left.tm} °C`,
                coords: `${count(leftStart)}–${count(leftEnd)} bp (sense)`,
              })
            }
            onMouseLeave={() => setHoveredItem(null)}
          >
            <line
              x1={leftX1}
              y1={trackY - 24}
              x2={leftX2}
              y2={trackY - 24}
              className="stroke-primary"
              strokeWidth="4"
              strokeLinecap="round"
              markerEnd={`url(#${mapId}-arrow-fwd)`}
            />
            {/* Connecting dashed line down to track */}
            <line
              x1={leftX1}
              y1={trackY - 24}
              x2={leftX1}
              y2={trackY - 10}
              className="stroke-primary/50"
              strokeWidth="1"
              strokeDasharray="2,2"
            />
            <line
              x1={leftX2}
              y1={trackY - 24}
              x2={leftX2}
              y2={trackY - 10}
              className="stroke-primary/50"
              strokeWidth="1"
              strokeDasharray="2,2"
            />
            <text
              x={Math.max(paddingX + 10, (leftX1 + leftX2) / 2)}
              y={trackY - 32}
              textAnchor="middle"
              className="fill-primary font-mono text-xs font-semibold"
            >
              Fwd ({pair.left.length}nt)
            </text>
          </g>

          {/* Reverse primer (Right, 5' -> 3' pointing Left) */}
          <g
            className="cursor-pointer transition-opacity hover:opacity-90"
            onMouseEnter={() =>
              setHoveredItem({
                label: "Reverse Primer",
                details: `${pair.right.length} nt · ${pair.right.gc_percent}% GC · ${pair.right.tm} °C`,
                coords: `${count(rightStart)}–${count(rightEnd)} bp (antisense)`,
              })
            }
            onMouseLeave={() => setHoveredItem(null)}
          >
            <line
              x1={rightX2}
              y1={trackY + 24}
              x2={rightX1}
              y2={trackY + 24}
              className="stroke-chart-4"
              strokeWidth="4"
              strokeLinecap="round"
              markerEnd={`url(#${mapId}-arrow-rev)`}
            />
            {/* Connecting dashed line up to track */}
            <line
              x1={rightX1}
              y1={trackY + 10}
              x2={rightX1}
              y2={trackY + 24}
              className="stroke-chart-4/50"
              strokeWidth="1"
              strokeDasharray="2,2"
            />
            <line
              x1={rightX2}
              y1={trackY + 10}
              x2={rightX2}
              y2={trackY + 24}
              className="stroke-chart-4/50"
              strokeWidth="1"
              strokeDasharray="2,2"
            />
            <text
              x={Math.min(svgWidth - paddingX - 10, (rightX1 + rightX2) / 2)}
              y={trackY + 40}
              textAnchor="middle"
              className="fill-chart-4 font-mono text-xs font-semibold"
            >
              Rev ({pair.right.length}nt)
            </text>
          </g>

          {/* Internal Probe if present */}
          {probe ? (
            <g
              className="cursor-pointer transition-opacity hover:opacity-90"
              onMouseEnter={() =>
                setHoveredItem({
                  label: "Fluorogenic Probe",
                  details: `${probe.length} nt ${probe.tm ? `· ${probe.tm} °C` : ""}`,
                  coords: `${count(probe.start)}–${count(probe.start + probe.length - 1)} bp`,
                })
              }
              onMouseLeave={() => setHoveredItem(null)}
            >
              <rect
                x={probeX1}
                y={trackY - 4}
                width={probeWidth}
                height={8}
                rx="2"
                className="fill-chart-5 stroke-chart-5"
                strokeWidth="1.5"
              />
              <text
                x={(probeX1 + probeX2) / 2}
                y={trackY - 10}
                textAnchor="middle"
                className="fill-chart-5 font-mono text-[10px] font-semibold"
              >
                Probe
              </text>
            </g>
          ) : null}

          {/* Coordinate axis ticks & labels at the bottom */}
          {uniqueTicks.map((tick) => {
            const x = toX(tick);
            return (
              <g key={tick}>
                <line
                  x1={x}
                  y1={trackY + 48}
                  x2={x}
                  y2={trackY + 54}
                  className="stroke-muted-foreground/50"
                  strokeWidth="1"
                />
                <text
                  x={x}
                  y={trackY + 66}
                  textAnchor="middle"
                  className="fill-muted-foreground font-mono text-[10px] tabular-nums"
                >
                  {count(tick)}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Dynamic Hover Details Bar */}
      <div className="flex min-h-6 items-center justify-between rounded bg-muted/40 px-2.5 py-1 text-xs">
        {hoveredItem ? (
          <>
            <span className="font-medium text-foreground">
              {hoveredItem.label}:{" "}
              <span className="font-normal text-muted-foreground">{hoveredItem.details}</span>
            </span>
            <span className="font-mono text-muted-foreground tabular-nums">
              {hoveredItem.coords}
            </span>
          </>
        ) : (
          <span className="text-xs text-muted-foreground">
            Hover over primers, probe or amplicon to inspect exact coordinates and properties.
          </span>
        )}
      </div>
    </div>
  );
}

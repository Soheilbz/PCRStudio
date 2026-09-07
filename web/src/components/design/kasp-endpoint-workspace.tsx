"use client";

import { useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { kaspPlotBounds, parseKaspEndpoint, type KaspEndpointRow } from "@/lib/kasp-endpoint";

export function KaspEndpointWorkspace() {
  const [text, setText] = useState("");
  const parsed = useMemo(() => {
    if (!text.trim()) return { value: null, error: "" };
    try {
      return { value: parseKaspEndpoint(text), error: "" };
    } catch (error) {
      return {
        value: null,
        error: error instanceof Error ? error.message : "Endpoint data could not be parsed.",
      };
    }
  }, [text]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">KASP endpoint evidence workspace</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-md border border-dashed border-border/60 bg-surface-wash/25 p-3 text-xs leading-relaxed text-muted-foreground">
          Paste a flat CSV/TSV export containing FAM and HEX values. PCRStudio plots the measured
          endpoint evidence and preserves provider/software calls when present; it does{" "}
          <strong>not</strong> invent cluster thresholds or auto-call unlabelled wells.
        </div>
        <div>
          <Label htmlFor="kasp-endpoint-paste" className="text-xs">
            Endpoint table · FAM = X, HEX = Y
          </Label>
          <textarea
            id="kasp-endpoint-paste"
            rows={8}
            spellCheck={false}
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder={
              "Sample,Well,FAM,HEX,Call,Control\nS1,A01,1240,220,AA,known-genotype\nS2,A02,680,710,AB,known-genotype"
            }
            className="mt-1 w-full rounded-lg border border-border/70 bg-surface-wash/35 p-2 font-mono text-xs"
          />
        </div>
        {parsed.error ? <p className="text-xs text-destructive">{parsed.error}</p> : null}
        {parsed.value ? (
          <>
            <div className="grid gap-3 text-xs sm:grid-cols-3">
              <Fact label="Rows plotted" value={String(parsed.value.rows.length)} />
              <Fact
                label="Calls in source"
                value={Object.entries(parsed.value.callSummary)
                  .map(([key, value]) => `${key}: ${value}`)
                  .join(" · ")}
              />
              <Fact label="Decision impact" value="none on primer ranking" />
            </div>
            <KaspScatter rows={parsed.value.rows} />
            {parsed.value.warnings.length ? (
              <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">
                {parsed.value.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            ) : null}
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}

function KaspScatter({ rows }: { rows: KaspEndpointRow[] }) {
  const bounds = kaspPlotBounds(rows);
  const width = 520;
  const height = 340;
  const pad = 44;
  const x = (value: number) =>
    pad +
    ((value - bounds.xMin) / Math.max(bounds.xMax - bounds.xMin, Number.EPSILON)) *
      (width - pad * 2);
  const y = (value: number) =>
    height -
    pad -
    ((value - bounds.yMin) / Math.max(bounds.yMax - bounds.yMin, Number.EPSILON)) *
      (height - pad * 2);
  return (
    <div className="overflow-x-auto rounded-lg border border-border/60 bg-background/40 p-2">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full min-w-[480px]"
        role="img"
        aria-label="KASP endpoint scatter plot with FAM on X and HEX on Y"
      >
        <line
          x1={pad}
          y1={height - pad}
          x2={width - pad}
          y2={height - pad}
          className="stroke-border"
        />
        <line x1={pad} y1={pad} x2={pad} y2={height - pad} className="stroke-border" />
        <text
          x={width / 2}
          y={height - 10}
          textAnchor="middle"
          className="fill-muted-foreground text-xs"
        >
          FAM fluorescence · X
        </text>
        <text
          x={14}
          y={height / 2}
          textAnchor="middle"
          transform={`rotate(-90 14 ${height / 2})`}
          className="fill-muted-foreground text-xs"
        >
          HEX fluorescence · Y
        </text>
        {rows.map((row, index) => (
          <circle
            key={`${row.sampleId}-${row.well ?? index}`}
            cx={x(row.fam)}
            cy={y(row.hex)}
            r={4}
            className="fill-primary/70 stroke-background"
          >
            <title>{`${row.sampleId}${row.well ? ` · ${row.well}` : ""} · FAM ${row.fam} · HEX ${row.hex} · ${row.call ?? "unreviewed"}${row.control ? ` · ${row.control}` : ""}`}</title>
          </circle>
        ))}
      </svg>
      <p className="px-2 pb-1 text-xs leading-relaxed text-muted-foreground">
        Axes are scaled only for visualization. Cluster identity remains source/user-reviewed
        evidence; no geometric boundary is synthesized by this plot.
      </p>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 font-medium">{value || "not recorded"}</dd>
    </div>
  );
}

"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Row = {
  target: string;
  reporter?: string;
  channel?: string;
  amplitudeClass?: string;
  primerEachNm?: number;
  probeNm?: number;
};

function rowsFrom(raw: string): Row[] {
  if (!raw.trim()) return [];
  try {
    const value = JSON.parse(raw);
    return Array.isArray(value)
      ? value.filter((row): row is Row => Boolean(row && typeof row === "object"))
      : [];
  } catch {
    return [];
  }
}

export function DigitalMultiplexEditor({
  mode,
  rawValue,
  onChange,
}: {
  mode: string;
  rawValue: string;
  onChange: (next: string) => void;
}) {
  const rows = rowsFrom(rawValue);
  const write = (next: Row[]) => onChange(next.length ? JSON.stringify(next) : "");
  const update = (index: number, key: keyof Row, value: string) => {
    const next = rows.map((row, i) => {
      if (i !== index) return row;
      if (key === "primerEachNm" || key === "probeNm") {
        const numeric = value.trim() ? Number(value) : undefined;
        return { ...row, [key]: Number.isFinite(numeric) ? numeric : undefined };
      }
      return { ...row, [key]: value.trim() || undefined };
    });
    write(next);
  };

  if (!mode || mode === "none") return null;

  return (
    <div className="space-y-3 rounded-lg border border-border/60 bg-background/30 p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h4 className="text-xs font-medium">Digital multiplex panel</h4>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            This is an optical/amplitude planning and run-evidence contract. The dye-flanking engine
            does not invent peer probe assays, thresholds, rain gates or cluster boundaries. Channel
            mode requires unique channels; amplitude/hybrid modes require an explicit amplitude
            class for every target.
          </p>
        </div>
        <button
          type="button"
          onClick={() => write([...rows, { target: "" }])}
          className="rounded-md border border-border/70 px-2 py-1 text-xs"
        >
          Add target
        </button>
      </div>
      {rows.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          Add at least two targets for multiplex planning.
        </p>
      ) : null}
      {rows.map((row, index) => (
        <div
          key={`${index}-${row.target}`}
          className="grid gap-2 rounded-md border border-border/50 p-2 sm:grid-cols-2 lg:grid-cols-3"
        >
          <Input
            aria-label={`Digital multiplex target ${index + 1}`}
            value={row.target ?? ""}
            onChange={(e) => update(index, "target", e.target.value)}
            placeholder="Target identity"
          />
          <Input
            aria-label={`Digital multiplex reporter ${index + 1}`}
            value={row.reporter ?? ""}
            onChange={(e) => update(index, "reporter", e.target.value)}
            placeholder="Reporter / dye"
          />
          <Input
            aria-label={`Digital multiplex channel ${index + 1}`}
            value={row.channel ?? ""}
            onChange={(e) => update(index, "channel", e.target.value)}
            placeholder="Instrument channel"
          />
          {mode === "amplitude" || mode === "hybrid" ? (
            <Input
              aria-label={`Digital multiplex amplitude class ${index + 1}`}
              value={row.amplitudeClass ?? ""}
              onChange={(e) => update(index, "amplitudeClass", e.target.value)}
              placeholder="Amplitude class / planned level"
            />
          ) : null}
          <div>
            <Label className="sr-only" htmlFor={`digital-primer-${index}`}>
              Primer each nM
            </Label>
            <Input
              id={`digital-primer-${index}`}
              inputMode="decimal"
              value={row.primerEachNm ?? ""}
              onChange={(e) => update(index, "primerEachNm", e.target.value)}
              placeholder="Primer each nM (planned/measured)"
            />
          </div>
          <div>
            <Label className="sr-only" htmlFor={`digital-probe-${index}`}>
              Probe nM
            </Label>
            <Input
              id={`digital-probe-${index}`}
              inputMode="decimal"
              value={row.probeNm ?? ""}
              onChange={(e) => update(index, "probeNm", e.target.value)}
              placeholder="Probe nM (planned/measured)"
            />
          </div>
          <button
            type="button"
            onClick={() => write(rows.filter((_, i) => i !== index))}
            className="h-9 rounded-md border border-border/70 px-2 text-xs"
          >
            Remove target
          </button>
        </div>
      ))}
    </div>
  );
}

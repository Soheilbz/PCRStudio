"use client";

import { Input } from "@/components/ui/input";

export type ProbeMultiplexTarget = {
  target: string;
  reporter: string;
  quencher: string;
  internalQuencher?: string;
  channel?: string;
  forwardPrimer?: string;
  reversePrimer?: string;
  probeSequence?: string;
};

function parseRows(raw: string): ProbeMultiplexTarget[] {
  if (!raw.trim()) return [];
  try {
    const value = JSON.parse(raw);
    if (!Array.isArray(value)) return [];
    return value.filter((row): row is ProbeMultiplexTarget =>
      Boolean(row && typeof row === "object"),
    );
  } catch {
    return [];
  }
}

export function ProbeMultiplexEditor({
  rawValue,
  reporters,
  quenchers,
  internalQuenchers,
  onChange,
}: {
  rawValue: string;
  reporters: string[];
  quenchers: string[];
  internalQuenchers: string[];
  onChange: (next: string) => void;
}) {
  const rows = parseRows(rawValue);
  const write = (next: ProbeMultiplexTarget[]) => onChange(next.length ? JSON.stringify(next) : "");
  const update = (index: number, key: keyof ProbeMultiplexTarget, value: string) => {
    const next = rows.map((row, i) => (i === index ? { ...row, [key]: value || undefined } : row));
    write(next);
  };
  const remove = (index: number) => write(rows.filter((_, i) => i !== index));
  const add = () =>
    write([...rows, { target: "", reporter: reporters[0] ?? "", quencher: quenchers[0] ?? "" }]);

  return (
    <div
      className="space-y-2 rounded-lg border border-border/60 bg-background/30 p-3"
      aria-labelledby="probeMultiplexTargetsLabel"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <span id="probeMultiplexTargetsLabel" className="text-xs font-medium">
            Multiplex targets (optional)
          </span>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            Reporter/quencher identity is validated against the selected chemistry and explicit
            channel names must be unique. Supply the peer forward primer, reverse primer and probe
            whenever they are known so PCRStudio can calculate the all-vs-all cross-assay
            interaction matrix; no universal rejection threshold is invented.
          </p>
        </div>
        <button
          type="button"
          onClick={add}
          className="rounded-md border border-border/70 px-2 py-1 text-xs"
        >
          Add target
        </button>
      </div>
      {rows.length === 0 ? (
        <p className="text-xs text-muted-foreground">No multiplex targets defined.</p>
      ) : null}
      {rows.map((row, index) => (
        <div
          key={`${index}-${row.target}`}
          className="grid gap-2 rounded-md border border-border/50 p-2 sm:grid-cols-2 lg:grid-cols-3"
        >
          <Input
            aria-label={`Multiplex target ${index + 1} name`}
            value={row.target ?? ""}
            onChange={(e) => update(index, "target", e.target.value)}
            placeholder="Target name"
          />
          <select
            aria-label={`Multiplex target ${index + 1} reporter`}
            value={row.reporter ?? ""}
            onChange={(e) => update(index, "reporter", e.target.value)}
            className="h-9 rounded-md border border-border/70 bg-surface-wash/35 px-2 text-sm"
          >
            <option value="">Reporter</option>
            {reporters.map((x) => (
              <option key={x} value={x}>
                {x}
              </option>
            ))}
          </select>
          <select
            aria-label={`Multiplex target ${index + 1} quencher`}
            value={row.quencher ?? ""}
            onChange={(e) => update(index, "quencher", e.target.value)}
            className="h-9 rounded-md border border-border/70 bg-surface-wash/35 px-2 text-sm"
          >
            <option value="">Quencher</option>
            {quenchers.map((x) => (
              <option key={x} value={x}>
                {x}
              </option>
            ))}
          </select>
          <select
            aria-label={`Multiplex target ${index + 1} internal quencher`}
            value={row.internalQuencher ?? ""}
            onChange={(e) => update(index, "internalQuencher", e.target.value)}
            className="h-9 rounded-md border border-border/70 bg-surface-wash/35 px-2 text-sm"
          >
            <option value="">No internal quencher</option>
            {internalQuenchers.map((x) => (
              <option key={x} value={x}>
                {x}
              </option>
            ))}
          </select>
          <Input
            aria-label={`Multiplex target ${index + 1} channel`}
            value={row.channel ?? ""}
            onChange={(e) => update(index, "channel", e.target.value)}
            placeholder="Instrument channel"
          />
          <Input
            aria-label={`Multiplex target ${index + 1} forward primer`}
            value={row.forwardPrimer ?? ""}
            onChange={(e) => update(index, "forwardPrimer", e.target.value)}
            placeholder="Peer forward primer (5′→3′)"
          />
          <Input
            aria-label={`Multiplex target ${index + 1} reverse primer`}
            value={row.reversePrimer ?? ""}
            onChange={(e) => update(index, "reversePrimer", e.target.value)}
            placeholder="Peer reverse primer (5′→3′)"
          />
          <Input
            aria-label={`Multiplex target ${index + 1} probe sequence`}
            value={row.probeSequence ?? ""}
            onChange={(e) => update(index, "probeSequence", e.target.value)}
            placeholder="Peer probe sequence (5′→3′)"
          />
          <button
            type="button"
            onClick={() => remove(index)}
            className="h-9 rounded-md border border-border/70 px-2 text-xs"
          >
            Remove target
          </button>
        </div>
      ))}
    </div>
  );
}

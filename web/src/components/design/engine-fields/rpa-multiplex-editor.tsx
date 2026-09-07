"use client";
import { Input } from "@/components/ui/input";

type Row = {
  target: string;
  forwardPrimer: string;
  reversePrimer: string;
  detectionIdentity?: string;
  empiricalEvidenceRef?: string;
};
function parse(raw: string): Row[] {
  try {
    const v = JSON.parse(raw || "[]");
    return Array.isArray(v) ? v : [];
  } catch {
    return [];
  }
}
export function RpaMultiplexEditor({
  rawValue,
  onChange,
}: {
  rawValue: string;
  onChange: (v: string) => void;
}) {
  const rows = parse(rawValue);
  const write = (r: Row[]) => onChange(r.length ? JSON.stringify(r) : "");
  const update = (i: number, k: keyof Row, v: string) =>
    write(rows.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  return (
    <div className="space-y-2 rounded-md border border-border/60 p-2">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          Selected peer RPA assays. Final panel performance remains empirical; Scientific-Strict
          requires an empirical evidence reference for every peer.
        </p>
        <button
          type="button"
          className="rounded border px-2 py-1 text-xs"
          onClick={() => write([...rows, { target: "", forwardPrimer: "", reversePrimer: "" }])}
        >
          Add peer
        </button>
      </div>
      {rows.map((r, i) => (
        <div key={i} className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          <Input
            value={r.target || ""}
            onChange={(e) => update(i, "target", e.target.value)}
            placeholder="Peer target"
          />
          <Input
            value={r.forwardPrimer || ""}
            onChange={(e) => update(i, "forwardPrimer", e.target.value)}
            placeholder="Selected forward 5′→3′"
          />
          <Input
            value={r.reversePrimer || ""}
            onChange={(e) => update(i, "reversePrimer", e.target.value)}
            placeholder="Selected reverse 5′→3′"
          />
          <Input
            value={r.detectionIdentity || ""}
            onChange={(e) => update(i, "detectionIdentity", e.target.value)}
            placeholder="Detection identity"
          />
          <Input
            value={r.empiricalEvidenceRef || ""}
            onChange={(e) => update(i, "empiricalEvidenceRef", e.target.value)}
            placeholder="Empirical evidence ref"
          />
          <button
            type="button"
            className="rounded border px-2 py-1 text-xs"
            onClick={() => write(rows.filter((_, j) => j !== i))}
          >
            Remove
          </button>
        </div>
      ))}
    </div>
  );
}

"use client";
import { Input } from "@/components/ui/input";
type Row = {
  target: string;
  method: string;
  reporter: string;
  channel: string;
  modifiedOligoRole: string;
  setSha256: string;
  authorityId: string;
  empiricalEvidenceRef: string;
};
function parse(raw: string): Row[] {
  try {
    const v = JSON.parse(raw || "[]");
    return Array.isArray(v) ? v : [];
  } catch {
    return [];
  }
}
export function LampMultiplexEditor({
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
          Evidence-bound multiplex LAMP plan. PCRStudio does not generate
          DARQ/QUASR/FLOS/assimilation modifications or infer target-specific signal.
        </p>
        <button
          type="button"
          className="rounded border px-2 py-1 text-xs"
          onClick={() =>
            write([
              ...rows,
              {
                target: "",
                method: "darq",
                reporter: "",
                channel: "",
                modifiedOligoRole: "",
                setSha256: "",
                authorityId: "",
                empiricalEvidenceRef: "",
              },
            ])
          }
        >
          Add peer
        </button>
      </div>
      {rows.map((r, i) => (
        <div key={i} className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <Input
            value={r.target || ""}
            onChange={(e) => update(i, "target", e.target.value)}
            placeholder="Peer target"
          />
          <select
            value={r.method || "darq"}
            onChange={(e) => update(i, "method", e.target.value)}
            className="h-9 rounded-md border bg-background px-2 text-xs"
          >
            <option value="darq">DARQ</option>
            <option value="quasr">QUASR</option>
            <option value="flos">FLOS</option>
            <option value="assimilation-probe">Assimilation probe</option>
            <option value="other-reviewed">Other reviewed method</option>
          </select>
          <Input
            value={r.reporter || ""}
            onChange={(e) => update(i, "reporter", e.target.value)}
            placeholder="Reporter"
          />
          <Input
            value={r.channel || ""}
            onChange={(e) => update(i, "channel", e.target.value)}
            placeholder="Channel"
          />
          <Input
            value={r.modifiedOligoRole || ""}
            onChange={(e) => update(i, "modifiedOligoRole", e.target.value)}
            placeholder="Modified oligo role"
          />
          <Input
            value={r.setSha256 || ""}
            onChange={(e) => update(i, "setSha256", e.target.value)}
            placeholder="Peer set SHA-256"
          />
          <Input
            value={r.authorityId || ""}
            onChange={(e) => update(i, "authorityId", e.target.value)}
            placeholder="Method/SOP authority ID"
          />
          <Input
            value={r.empiricalEvidenceRef || ""}
            onChange={(e) => update(i, "empiricalEvidenceRef", e.target.value)}
            placeholder="Empirical signal evidence ref"
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

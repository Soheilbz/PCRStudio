/**
 * Local KASP endpoint-data parser.
 *
 * This module deliberately does not classify fluorescence into genotypes.
 * Provider/software calls may be retained as evidence, but PCRStudio does not
 * invent cluster thresholds from FAM/HEX values or silently convert a plot into
 * a validated call set.
 */

export type KaspEndpointRow = {
  sampleId: string;
  well?: string;
  fam: number;
  hex: number;
  call?: string;
  control?: string;
  provider?: string;
  software?: string;
};

export type KaspEndpointParse = {
  rows: KaspEndpointRow[];
  delimiter: "," | "\t";
  warnings: string[];
  callSummary: Record<string, number>;
};

const NORMALIZED_HEADERS: Record<string, string> = {
  sample: "sampleId",
  sampleid: "sampleId",
  sample_id: "sampleId",
  id: "sampleId",
  name: "sampleId",
  well: "well",
  position: "well",
  fam: "fam",
  famrfu: "fam",
  fam_rfu: "fam",
  x: "fam",
  hex: "hex",
  hexrfu: "hex",
  hex_rfu: "hex",
  vic: "hex",
  y: "hex",
  call: "call",
  genotype: "call",
  cluster: "call",
  control: "control",
  controltype: "control",
  control_type: "control",
  provider: "provider",
  vendor: "provider",
  instrumentprovider: "provider",
  software: "software",
  softwarename: "software",
  analysissoftware: "software",
};

function norm(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[\s()./%-]+/gu, "")
    .replace(/[^a-z0-9_]/gu, "");
}

function splitLine(line: string, delimiter: "," | "\t"): string[] {
  // Endpoint exports used here are flat tables. Quoted comma-containing fields
  // are intentionally not guessed; users should export TSV or a clean CSV.
  return line.split(delimiter).map((part) => part.trim().replace(/^"|"$/gu, ""));
}

export function parseKaspEndpoint(text: string): KaspEndpointParse {
  const lines = text
    .replace(/^\uFEFF/u, "")
    .split(/\r?\n/u)
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length < 2) throw new Error("Endpoint data need a header and at least one sample row.");

  const delimiter: "," | "\t" = lines[0]!.includes("\t") ? "\t" : ",";
  const rawHeaders = splitLine(lines[0]!, delimiter);
  const mapped = rawHeaders.map((header) => NORMALIZED_HEADERS[norm(header)] ?? "");
  const famIndex = mapped.indexOf("fam");
  const hexIndex = mapped.indexOf("hex");
  const sampleIndex = mapped.indexOf("sampleId");
  if (famIndex < 0 || hexIndex < 0) {
    throw new Error("Endpoint table must contain FAM and HEX fluorescence columns.");
  }

  const warnings: string[] = [];
  if (sampleIndex < 0)
    warnings.push("No sample-ID column was detected; row numbers are used as local labels.");
  const rows: KaspEndpointRow[] = [];
  for (let rowIndex = 1; rowIndex < lines.length; rowIndex += 1) {
    const values = splitLine(lines[rowIndex]!, delimiter);
    const fam = Number(values[famIndex]);
    const hex = Number(values[hexIndex]);
    if (!Number.isFinite(fam) || !Number.isFinite(hex)) {
      warnings.push(`Row ${rowIndex + 1} was skipped because FAM/HEX were not finite numbers.`);
      continue;
    }
    const get = (field: string): string | undefined => {
      const index = mapped.indexOf(field);
      const value = index >= 0 ? values[index]?.trim() : undefined;
      return value || undefined;
    };
    rows.push({
      sampleId: get("sampleId") ?? `row-${rowIndex}`,
      well: get("well"),
      fam,
      hex,
      call: get("call"),
      control: get("control"),
      provider: get("provider"),
      software: get("software"),
    });
  }
  if (!rows.length) throw new Error("No endpoint rows with numeric FAM and HEX values were found.");

  const callSummary: Record<string, number> = {};
  for (const row of rows) {
    const call = row.call?.trim() || "unreviewed";
    callSummary[call] = (callSummary[call] ?? 0) + 1;
  }
  return { rows, delimiter, warnings, callSummary };
}

export function kaspPlotBounds(rows: KaspEndpointRow[]) {
  const fam = rows.map((row) => row.fam);
  const hex = rows.map((row) => row.hex);
  const xMin = Math.min(...fam);
  const xMax = Math.max(...fam);
  const yMin = Math.min(...hex);
  const yMax = Math.max(...hex);
  const xPad = Math.max((xMax - xMin) * 0.05, Math.abs(xMax) * 0.01, 1);
  const yPad = Math.max((yMax - yMin) * 0.05, Math.abs(yMax) * 0.01, 1);
  return { xMin: xMin - xPad, xMax: xMax + xPad, yMin: yMin - yPad, yMax: yMax + yPad };
}

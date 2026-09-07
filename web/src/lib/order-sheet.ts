/**
 * Turning a design into the file somebody actually orders from.
 *
 * One builder for every engine, because there were thirteen result views and
 * one download button. The other twelve offered a clipboard copy of names and
 * sequences and nothing else — so a tiling scheme of sixteen oligos, or a LAMP
 * set whose two composites must not be ordered by their whole-molecule melting
 * temperature, left the application as tab-separated text with the part that
 * mattered stripped out.
 *
 * Three things here are not obvious and all three are the reason this is a
 * module rather than four lines inside a component.
 *
 * **A field can contain a comma.** A target named "TP53, exon 7" splits one row
 * into two and every column after it is wrong, silently, in a file somebody
 * pastes into an ordering form.
 *
 * **A field can be a formula.** Excel and Sheets execute a cell beginning `=`,
 * `+`, `-` or `@`, and every name in this file comes from something a person
 * typed. `=1+1` is the harmless demonstration; the real ones reach the network.
 * Prefixing with a tab is the standard defence and keeps the value readable.
 *
 * **The temperature means nothing without the buffer.** A melting temperature
 * is computed for a particular salt and oligo concentration, and the same
 * primer in a different reaction melts several degrees away. A sheet carrying
 * the number and not the conditions is a sheet nobody can check.
 */

/** One line of an order sheet, in the shape every engine already emits. */
export interface OrderLine {
  name: string;
  sequence: string;
  length: number;
  gc_percent: number;
  /** Absent for a degenerate oligo, which does not have one — see `tm_min`. */
  tm?: number;
  /**
   * A degenerate oligo is a mixture, and a mixture melts over a range. The two
   * ends are reported instead of a single number, because the single number
   * would be the melting temperature of no molecule actually in the tube.
   */
  tm_min?: number;
  tm_max?: number;
  /** How many distinct sequences the one well contains. */
  degeneracy?: number;
  /** Some engines add one, and it is usually the thing that must not be lost. */
  note?: string;
  /** Tiling puts each oligo in a pool; a plate is loaded from this. */
  pool?: number;
  /** Assembly puts each primer in its own reaction. */
  tube?: string;
}

/** The reaction the temperatures were computed in. */
export interface Conditions {
  polymerase?: string;
  polymerase_name?: string;
  mv_conc?: number;
  dv_conc?: number;
  dntp_conc?: number;
  dna_conc?: number;
  /** `{ name, salt_correction }` — the nearest-neighbour table and the salt term. */
  model?: { name: string; salt_correction: string };
}

/** Characters a spreadsheet will execute if they start a cell. */
const FORMULA_START = /^[=+\-@\t\r]/;

/**
 * One CSV field: escaped, and defused if it would otherwise run.
 *
 * The tab prefix is what stops a spreadsheet treating the value as a formula.
 * It is inside the quotes, so the cell still reads as the original text.
 */
function field(value: unknown): string {
  const text = value === null || value === undefined ? "" : String(value);
  const safe = FORMULA_START.test(text) ? `\t${text}` : text;
  return `"${safe.replace(/"/g, '""')}"`;
}

/** A filename that every operating system will accept, dated so two do not collide. */
export function orderSheetFilename(
  targetName: string | undefined,
  kind = "primers",
  extension = "csv",
): string {
  const cleaned = (targetName ?? "")
    .replace(/[^\w.-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
  const today = new Date().toISOString().slice(0, 10);
  return `${cleaned || kind}-${today}.${extension}`;
}

/**
 * The whole sheet.
 *
 * The reaction goes in as commented lines above the table rather than as extra
 * columns repeated on every row: a spreadsheet reads it as text at the top,
 * which is where somebody looks for it, and the table underneath still imports
 * as a table.
 */
export function toCsv(lines: OrderLine[], conditions?: Conditions): string {
  const preamble: string[] = [];
  if (conditions) {
    const salts = [
      conditions.mv_conc !== undefined ? `monovalent ${conditions.mv_conc} mM` : null,
      conditions.dv_conc !== undefined ? `divalent ${conditions.dv_conc} mM` : null,
      conditions.dntp_conc !== undefined ? `dNTP ${conditions.dntp_conc} mM` : null,
      conditions.dna_conc !== undefined ? `Tm oligo input ${conditions.dna_conc} nM` : null,
    ].filter(Boolean);

    preamble.push(
      "# Melting temperatures below are computed for this reaction, not in general.",
      `# Reaction: ${conditions.polymerase_name ?? conditions.polymerase ?? "unspecified"}`,
      salts.length ? `# Conditions: ${salts.join(", ")}` : "# Conditions: unspecified",
      conditions.model
        ? `# Model: ${conditions.model.name}, salt correction ${conditions.model.salt_correction}`
        : "",
    );
  }

  /*
   * Columns are chosen from what the lines actually carry, not fixed in
   * advance. A standard pair should not export three empty ones, and a
   * degenerate pool must not export a `tm_celsius` — it does not have one.
   */
  const columns: Array<[string, (line: OrderLine) => unknown]> = [
    ["name", (line) => line.name],
    ["sequence", (line) => line.sequence],
    ["length_nt", (line) => line.length],
    ["gc_percent", (line) => line.gc_percent],
  ];
  const has = (pick: (line: OrderLine) => unknown) =>
    lines.some((line) => pick(line) !== undefined && pick(line) !== "");

  if (has((line) => line.tm)) columns.push(["tm_celsius", (line) => line.tm]);
  if (has((line) => line.tm_min)) {
    columns.push(
      ["tm_min_celsius", (line) => line.tm_min],
      ["tm_max_celsius", (line) => line.tm_max],
    );
  }
  if (has((line) => line.degeneracy)) {
    columns.push(["distinct_sequences", (line) => line.degeneracy]);
  }
  // One-based, because a plate's first pool is pool 1 everywhere except in code.
  if (has((line) => line.pool)) {
    columns.push(["pool", (line) => (line.pool === undefined ? "" : line.pool + 1)]);
  }
  if (has((line) => line.tube)) columns.push(["reaction", (line) => line.tube]);
  if (has((line) => line.note)) columns.push(["note", (line) => line.note]);

  const header = columns.map(([name]) => name);
  const rows = lines.map((line) => columns.map(([, pick]) => field(pick(line))).join(","));

  return [
    // Drop the placeholders for conditions this reaction did not report, then
    // separate the preamble from the table with exactly one blank line —
    // appended here rather than left as the last element of the preamble,
    // where it survived only when the model line happened to be missing.
    ...(preamble.length > 0 ? [...preamble.filter(Boolean), ""] : []),
    header.map(field).join(","),
    ...rows,
  ].join("\r\n");
}

/**
 * IDT (Integrated DNA Technologies) Bulk Input Format CSV.
 * Columns: Sequence Name, Sequence, Scale, Purification
 */
export function toIdtCsv(lines: OrderLine[], scale = "25nm", purification = "STD"): string {
  const header = ["Sequence Name", "Sequence", "Scale", "Purification"].map(field).join(",");
  const rows = lines.map((line) =>
    [field(line.name), field(line.sequence), field(scale), field(purification)].join(","),
  );
  return [header, ...rows].join("\r\n");
}

/**
 * Standard FASTA representation of oligos and optionally the amplicon product.
 */
export function toFasta(lines: OrderLine[], amplicon?: { name: string; sequence: string }): string {
  const chunks: string[] = [];
  for (const line of lines) {
    const details = [
      `${line.length}nt`,
      `${line.gc_percent}%GC`,
      line.tm
        ? `${line.tm}C`
        : line.tm_min && line.tm_max
          ? `${line.tm_min}-${line.tm_max}C`
          : null,
      line.note,
    ]
      .filter(Boolean)
      .join(" ");
    chunks.push(`>${line.name} ${details}\n${line.sequence}`);
  }
  if (amplicon && amplicon.sequence) {
    chunks.push(`>${amplicon.name}_amplicon ${amplicon.sequence.length}bp\n${amplicon.sequence}`);
  }
  return chunks.join("\n\n");
}

/** Hand the sheet to the browser as a file. */
export function downloadOrderSheet(
  lines: OrderLine[],
  targetName: string | undefined,
  conditions?: Conditions,
): void {
  // A byte-order mark, because Excel on Windows reads a BOM-less UTF-8 file as
  // the local code page — and then a °C or a primer named with an accent
  // arrives as mojibake in the one file somebody sends to a supplier.
  const blob = new Blob(["﻿", toCsv(lines, conditions)], {
    type: "text/csv;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = orderSheetFilename(targetName, "primers", "csv");
  link.click();
  // Some engines resolve the download asynchronously after click().
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Download in IDT Bulk Order format. */
export function downloadIdtOrderSheet(lines: OrderLine[], targetName: string | undefined): void {
  const blob = new Blob(["﻿", toIdtCsv(lines)], {
    type: "text/csv;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = orderSheetFilename(targetName, "idt-order", "csv");
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Download primers and amplicon as FASTA. */
export function downloadFasta(
  lines: OrderLine[],
  targetName: string | undefined,
  amplicon?: { name: string; sequence: string },
): void {
  const blob = new Blob([toFasta(lines, amplicon)], {
    type: "text/plain;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = orderSheetFilename(targetName, "primers", "fasta");
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** The clipboard form: what somebody pastes straight into an ordering box. */
export function toTabbed(lines: OrderLine[]): string {
  return lines.map((line) => `${line.name}\t${line.sequence}`).join("\n");
}

/**
 * The order lines for a degenerate design, which is the one case that cannot
 * reuse an engine's own order sheet — because `consensus-pair` does not emit
 * one.
 *
 * It lives here rather than in the view so that the file somebody downloads and
 * the table somebody reads are built by the same function. Two copies of this
 * mapping is exactly the arrangement where the table shows one degeneracy and
 * the spreadsheet shows another.
 */
export function degenerateLines(sites: Array<{ name: string; site: DegenerateSite }>): OrderLine[] {
  return sites.map(({ name, site }) => ({
    name,
    sequence: site.sequence,
    length: site.length,
    // The midpoint of the pool's range, at the one decimal every other engine
    // reports GC to — not the many that dividing by two produces.
    gc_percent: Math.round(((site.gc_min + site.gc_max) / 2) * 10) / 10,
    tm_min: site.tm_min,
    tm_max: site.tm_max,
    degeneracy: site.degeneracy,
    note:
      site.degeneracy > 1
        ? `Degenerate pool of ${site.degeneracy} sequences` +
          // Two sequences can differ at a position and still melt together, so
          // a spread is only worth stating when there is one.
          (site.tm_spread >= 0.05
            ? `, melting across ${site.tm_spread.toFixed(1)} °C`
            : ", all melting together")
        : undefined,
  }));
}

/** What a degenerate engine reports about one binding site. */
export interface DegenerateSite {
  sequence: string;
  length: number;
  gc_min: number;
  gc_max: number;
  tm_min: number;
  tm_max: number;
  tm_spread: number;
  degeneracy: number;
}

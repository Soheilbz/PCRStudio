import { describe, expect, it } from "vitest";

import universalReal from "./__fixtures__/universal-real.json";
import { degenerateLines, orderSheetFilename, toCsv, toTabbed } from "./order-sheet";

const NEWLINE = "\r\n";

const line = (over: Partial<Parameters<typeof toCsv>[0][number]> = {}) => ({
  name: "TP53_F",
  sequence: "ACGTACGTACGTACGTACGT",
  length: 20,
  gc_percent: 50,
  tm: 60.1,
  ...over,
});

describe("the order sheet a supplier receives", () => {
  it("keeps a name containing a comma in one column", () => {
    // The failure this guards against is silent: the row still parses, every
    // column after the comma is shifted by one, and the sequence ends up in
    // the length field of a file somebody pastes into an ordering form.
    const csv = toCsv([line({ name: "TP53, exon 7" })]);
    const row = csv.split(NEWLINE).at(-1)!;

    expect(row).toContain('"TP53, exon 7"');
    // Five fields, not six: the comma is inside the quotes.
    expect(row.split('","')).toHaveLength(5);
  });

  it("doubles a quote inside a field rather than ending it", () => {
    expect(toCsv([line({ name: 'the "good" one' })])).toContain('"the ""good"" one"');
  });

  it("stops a spreadsheet executing a name that starts like a formula", () => {
    // Excel and Sheets run a cell beginning = + - or @. Every name here comes
    // from something a person typed, so this is reachable input, and a formula
    // in a downloaded file is not a cosmetic problem.
    for (const dangerous of ["=1+1", "+SUM(A1)", "-2", "@import", '=HYPERLINK("http://x")']) {
      // The field opens with a quote and then a tab, which is what stops the
      // spreadsheet reading the rest as an expression. Quotes inside are
      // doubled by the ordinary escaping, so only the opening is checked.
      const row = toCsv([line({ name: dangerous })])
        .split(NEWLINE)
        .at(-1)!;
      expect(row, dangerous).toMatch(/^"\t/);
    }
  });

  it("leaves a name that merely contains a hyphen alone", () => {
    // The guard is on the first character. TP53-F is an ordinary name and must
    // not arrive with a tab in front of it.
    const csv = toCsv([line({ name: "TP53-F" })]);
    expect(csv).toContain('"TP53-F"');
    expect(csv).not.toContain('"\tTP53-F"');
  });

  it("carries the reaction the temperatures were computed in", () => {
    // A melting temperature without its buffer is a number nobody can check:
    // the same primer in a different salt melts degrees away.
    const csv = toCsv([line()], {
      polymerase_name: "Taq",
      mv_conc: 50,
      dv_conc: 1.5,
      dntp_conc: 0.2,
      dna_conc: 250,
      model: { name: "SantaLucia 1998", salt_correction: "Owczarzy 2004" },
    });

    expect(csv).toContain("# Reaction: Taq");
    expect(csv).toContain("monovalent 50 mM");
    expect(csv).toContain("Tm oligo input 250 nM");
    expect(csv).toContain("SantaLucia 1998");
    // Above the table, so a spreadsheet still imports the rows as rows.
    expect(csv.indexOf("# Reaction")).toBeLessThan(csv.indexOf('"name"'));
  });

  it("separates the preamble from the table by one blank line, model or no model", () => {
    /*
     * This is where the first version was wrong, and where the first test was
     * too: the blank line was the last element of the preamble, so it survived
     * only when the model line was absent and collapsed whenever it was
     * present. The fixture used to check this had no model, so the test agreed
     * with the bug.
     */
    const base = { polymerase_name: "Taq", mv_conc: 50 };
    const withModel = toCsv([line()], {
      ...base,
      model: { name: "SantaLucia 1998", salt_correction: "Owczarzy 2004" },
    });
    const withoutModel = toCsv([line()], base);

    for (const [what, csv] of [
      ["with a model", withModel],
      ["without one", withoutModel],
    ] as const) {
      expect(
        csv.split(NEWLINE).filter((one) => one === ""),
        what,
      ).toHaveLength(1);
      const lines = csv.split(NEWLINE);
      expect(
        lines[lines.indexOf('"name","sequence","length_nt","gc_percent","tm_celsius"') - 1],
        what,
      ).toBe("");
    }
  });

  it("writes no preamble at all when there is no reaction to report", () => {
    // Multiplex reports sequences and no reaction. A lone blank first line is
    // a stray row in a spreadsheet, not a separator.
    expect(toCsv([line()]).startsWith('"name"')).toBe(true);
  });

  it("omits the columns nothing filled", () => {
    const header = toCsv([line()]).split(NEWLINE)[0];

    expect(header).toBe('"name","sequence","length_nt","gc_percent","tm_celsius"');
    expect(header).not.toContain("note");
    expect(header).not.toContain("pool");
  });

  it("numbers a pool from one, the way a plate is labelled", () => {
    const rows = toCsv([line({ pool: 0 }), line({ name: "b", pool: 1 })])
      .split(NEWLINE)
      .slice(1);

    expect(rows[0]).toContain('"1"');
    expect(rows[1]).toContain('"2"');
  });

  it("names the file after the target, without the characters a filesystem refuses", () => {
    expect(orderSheetFilename("TP53/exon 7: draft")).toMatch(
      /^TP53-exon-7-draft-\d{4}-\d{2}-\d{2}\.csv$/,
    );
    expect(orderSheetFilename("")).toMatch(/^primers-/);
    expect(orderSheetFilename(undefined, "lamp-set")).toMatch(/^lamp-set-/);
    // A traversal in a download name is not exotic: the target name is typed
    // by whoever pasted the sequence.
    expect(orderSheetFilename("../../etc/passwd")).not.toContain("/");
  });

  it("hands the clipboard the two columns an ordering box accepts", () => {
    expect(toTabbed([line(), line({ name: "TP53_R" })])).toBe(
      "TP53_F\tACGTACGTACGTACGTACGT\nTP53_R\tACGTACGTACGTACGTACGT",
    );
  });
});

describe("a real degenerate design leaving the application", () => {
  // Genuine `consensus-pair` output: six isolates built from GenBank M19173.1
  // at 6 % divergence, put through the worker's own handler. It is a fixture
  // because this is the one engine that emits no order sheet, so its lines are
  // constructed here — and a construction is exactly the kind of thing that
  // quietly stops matching what the engine reports.
  const rows = universalReal.pairs.flatMap((pair, index) => [
    { name: `universal_${index + 1}F`, site: pair.left },
    { name: `universal_${index + 1}R`, site: pair.right },
  ]);

  it("carries the IUPAC codes rather than a collapsed consensus", () => {
    const lines = degenerateLines(rows);

    // Y, W and K are the whole point: they are how one pair covers a family.
    expect(lines.some((one) => /[RYSWKMBDHVN]/.test(one.sequence))).toBe(true);
    for (const [index, one] of lines.entries()) {
      expect(one.sequence).toBe(rows[index]!.site.sequence);
    }
  });

  it("never quotes one temperature for a pool that melts across a range", () => {
    const lines = degenerateLines(rows);
    const spread = lines.find((one) => one.tm_max! - one.tm_min! > 1);

    expect(spread, "the fixture should hold a genuinely spread pool").toBeDefined();
    expect(spread!.tm).toBeUndefined();
    expect(toCsv(lines)).not.toContain('"tm_celsius"');
  });

  it("says a pool melts together rather than across 0.0 degrees", () => {
    const lines = degenerateLines(rows);

    expect(lines.some((one) => one.note?.includes("all melting together"))).toBe(true);
    expect(toCsv(lines)).not.toContain("across 0.0");
  });

  it("reports GC to one decimal, like every other engine", () => {
    for (const one of degenerateLines(rows)) {
      expect(String(one.gc_percent)).toMatch(/^\d+(\.\d)?$/);
    }
  });

  it("names the reaction the temperatures came from, once", () => {
    const csv = toCsv(degenerateLines(rows), universalReal.reaction);

    expect(csv).toContain("Standard Taq");
    expect(csv).toContain("monovalent 50 mM");
    // Exactly one blank line between the conditions and the table.
    expect(csv.split(NEWLINE).filter((one) => one === "")).toHaveLength(1);
  });
});

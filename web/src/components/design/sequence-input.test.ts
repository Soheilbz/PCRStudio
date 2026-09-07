import { describe, expect, it } from "vitest";

import {
  approximateBases,
  normalizeSequenceFormatting,
  nucleotideSequenceForCase,
  nucleotideSequenceForMetrics,
  suspiciousNucleotideCharacters,
} from "./approximate-bases";

describe("approximateBases", () => {
  it("counts a bare sequence", () => {
    expect(approximateBases("ACGTACGT")).toBe(8);
  });

  it("ignores FASTA headers", () => {
    expect(approximateBases(">exon 5\nACGTACGT\nACGT")).toBe(12);
  });

  it("reads only the ORIGIN section of a GenBank record", () => {
    const genbank = [
      "LOCUS       pUC19                   2686 bp    DNA     circular",
      "DEFINITION  cloning vector",
      "FEATURES             Location/Qualifiers",
      "     gene            1..87",
      '                     /gene="lacZ"',
      "ORIGIN",
      "        1 acgacgtacg tacgtacgtt",
      "       21 acgtacgtac",
      "//",
    ].join("\n");
    // The words in the header and feature table are letters too, which is
    // exactly why everything above ORIGIN is skipped rather than filtered.
    expect(approximateBases(genbank)).toBe(30);
  });

  it("does not count alignment gaps", () => {
    expect(approximateBases(">a\nACGT--ACGT\n>b\nACGTAACGT-")).toBe(17);
  });

  it("counts U as a base", () => {
    expect(approximateBases("AUGCAUGC")).toBe(8);
  });

  it("does not count invalid symbols as bases in preview metrics", () => {
    expect(nucleotideSequenceForMetrics(">target\nACGT!--XZJ\n")).toBe("ACGT");
    expect(approximateBases(">target\nACGT!--XZJ\n")).toBe(4);
  });

  it("accepts indented FASTA headers and stops GenBank metrics at the terminator", () => {
    expect(nucleotideSequenceForMetrics("  >target\nACGT\n")).toBe("ACGT");
    expect(nucleotideSequenceForMetrics("ORIGIN\n  1 acgt\n//\nACGT")).toBe("ACGT");
  });

  it("detects lowercase only in nucleotide bodies, not FASTA descriptions", () => {
    expect(nucleotideSequenceForCase(">cloning vector pUC19c\nACGTACGT\n")).toBe("ACGTACGT");
    expect(nucleotideSequenceForCase(">target\nACgtACGT\n")).toBe("ACgtACGT");
  });
});

describe("sequence intake helpers", () => {
  it("reports alignment gaps instead of treating them as cleanable noise", () => {
    expect(suspiciousNucleotideCharacters(">target\nACGT--ACGT\n")).toEqual(["-"]);
  });

  it("reports digits in raw sequence instead of treating them as coordinates", () => {
    expect(suspiciousNucleotideCharacters("ACGT12ACGT")).toEqual(["1", "2"]);
  });

  it("ignores FASTA header punctuation and keeps unknown body symbols visible", () => {
    expect(suspiciousNucleotideCharacters(">target / sample\nACGT!\n")).toEqual(["!"]);
  });

  it("removes only whitespace and recognised GenBank coordinate prefixes", () => {
    const genbank = ["LOCUS       demo 10 bp", "ORIGIN", "        1 acgt--acgt!", "//"].join("\n");
    expect(normalizeSequenceFormatting(genbank)).toContain("acgt--acgt!");
    expect(normalizeSequenceFormatting("ACGT 12\nACG-")).toBe("ACGT12\nACG-");
  });
});

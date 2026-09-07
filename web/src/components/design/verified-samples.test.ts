import { createHash } from "node:crypto";

import { describe, expect, it } from "vitest";

import { VERIFIED_SAMPLE_TEMPLATES } from "./verified-samples";

function nucleotideSequence(fasta: string): string {
  return fasta
    .split(/\r?\n/)
    .filter((line) => line.trim() && !line.startsWith(">"))
    .join("")
    .replace(/\s+/g, "")
    .toUpperCase();
}

describe("verified onboarding examples", () => {
  it("keeps accession, declared length and sequence checksum coupled", () => {
    expect(VERIFIED_SAMPLE_TEMPLATES.length).toBeGreaterThan(0);

    for (const sample of VERIFIED_SAMPLE_TEMPLATES) {
      const sequence = nucleotideSequence(sample.sequence);
      expect(sequence).toHaveLength(sample.length);
      expect(createHash("sha256").update(sequence).digest("hex")).toBe(sample.sequenceSha256);
      expect(sample.sequence.startsWith(`>${sample.accession}`)).toBe(true);
    }
  });
});

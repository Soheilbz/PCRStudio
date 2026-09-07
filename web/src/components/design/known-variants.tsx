"use client";

/**
 * Positions this template is known to be polymorphic at.
 *
 * The `variant-masking` modifier was declared on Standard PCR from the first
 * commit and read by nothing — a label rather than a setting, in the way the
 * reverse-transcription modifier was before it. This is the control that makes
 * it one.
 *
 * It is not the same question as an arbitrary avoided region: these coordinates
 * specifically mean "known polymorphic position". Scientific-Strict treats a
 * position-only input conservatively and keeps every supplied coordinate out of
 * primer binding sites. Without alternate alleles, frequencies and chemistry
 * evidence, the interface must not invent a universal number of terminal bases
 * that are fatal while upstream positions are harmless.
 *
 * Positions are typed the way a sequence is read — counting from one — and
 * converted on the way down by the same function every other coordinate on
 * this page goes through.
 */

import { useMemo } from "react";

import { Textarea } from "@/components/ui/textarea";
import { FieldGroup } from "@/components/form-parts";
import { parseVariants } from "@/lib/variants";

export function KnownVariants({
  value,
  onChange,
  length,
}: {
  value: string;
  onChange: (next: string) => void;
  /** Bases in the template, so a position past the end is caught here. */
  length: number;
}) {
  const parsed = useMemo(() => parseVariants(value), [value]);
  const offTheEnd = length > 0 ? parsed.filter((p) => p > length) : [];
  const unique = new Set(parsed).size;

  return (
    <FieldGroup
      label="Positions you know vary"
      hint="A primer sitting on a common SNP works on one allele and not the other, which is a failure that shows up on some samples and not others. Paste positions, or VCF lines — the second column is read."
    >
      <div className="space-y-2">
        <Textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={"245, 1102, 1103\nor paste VCF lines"}
          rows={3}
          className="font-mono text-xs sm:max-w-sm"
          aria-label="Positions you know vary"
          aria-describedby="variants-read-back"
        />
        {/* Read back rather than left to trust: a box that silently ignored
            what was pasted would let somebody believe a primer had been
            checked when nothing had. */}
        <p id="variants-read-back" className="text-xs text-muted-foreground">
          {parsed.length === 0
            ? "Nothing read yet. Leave it empty and no primer is checked against a variant."
            : offTheEnd.length > 0
              ? `${unique} position${unique === 1 ? "" : "s"} read, but ${offTheEnd.length} of them sit past base ${length}. Fix those before running — a position that cannot be placed masks nothing.`
              : `${unique} position${unique === 1 ? "" : "s"} read. In Scientific-Strict, a returned primer does not overlap any supplied polymorphic coordinate.`}
        </p>
      </div>
    </FieldGroup>
  );
}

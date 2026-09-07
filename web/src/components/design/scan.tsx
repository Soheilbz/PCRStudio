"use client";

import { count } from "@/lib/numbers";
import type { BackgroundScan, OffTargets } from "@/lib/api/types";

/**
 * What a specificity scan found, in the words every result uses.
 *
 * Six workers scan and this is the only place their answer is described, for
 * the same reason there is only one function doing the scanning: a LAMP set
 * and a genotyping pair examined against the same genome must not come back
 * described differently.
 */

/**
 * How far the scan looked — three states, not two.
 *
 * A run older than the scan carries no block at all. A run with an empty
 * background box was checked against the pasted sequence and nothing else. A
 * run given a genome was checked against it. All three report zero unwanted
 * products, and only the third is a statement about the sample.
 */
export function ScanSummary({ background }: { background: BackgroundScan | undefined }) {
  if (!background) {
    return (
      <p className="rounded-xl border border-dashed border-border bg-surface-wash/30 px-4 py-3 text-xs leading-relaxed text-muted-foreground italic">
        Specificity was not recorded. This run predates the scan; run it again to have it checked.
      </p>
    );
  }

  const narrow = background.template_only || !background.checked;
  const methodNote = background.method
    ? ` Method: ${background.method.id}; this is a bounded screen, not a whole-database BLAST/Primer-BLAST result.`
    : "";
  return (
    <div
      className={
        narrow
          ? "rounded-xl border border-dashed border-border bg-surface-wash/30 px-4 py-3 text-xs leading-relaxed text-muted-foreground italic"
          : "rounded-xl border border-border/70 bg-surface-wash/40 px-4 py-3 text-xs leading-relaxed text-muted-foreground"
      }
    >
      <p>
        {narrow
          ? `${background.note}${methodNote}`
          : `Checked against ${count(background.bases)} bases across ${background.contigs} record(s), exhaustively for ungapped windows within a whole-primer budget of up to ${background.max_mismatches} definite mismatch(es). Terminal mismatches remain visible evidence rather than an exact-seed exclusion rule.${methodNote}`}
      </p>
      {background.ambiguous_bases ? (
        <p className="mt-1">
          Supplied background contains {count(background.ambiguous_bases)} IUPAC-ambiguous base(s);
          site matching preserves ambiguity bounds rather than silently rewriting them as exact
          sequence.
        </p>
      ) : null}
      {background.panel_sha256 ? (
        <p className="mt-1 font-mono text-xs break-all">
          Exclusivity panel SHA-256: {background.panel_sha256}
        </p>
      ) : null}
      {background.panel_identity_claim ? (
        <p className="mt-1">
          The fingerprint identifies the supplied normalized FASTA content; it does not certify
          taxonomic completeness or biological representativeness.
        </p>
      ) : null}
      {background.panel_provenance ? (
        <p className="mt-1">
          Exclusivity-panel provenance:{" "}
          <span className="text-foreground">{background.panel_provenance}</span>
        </p>
      ) : null}
      {background.panel_selection_rationale ? (
        <p className="mt-1">
          Panel-selection rationale:{" "}
          <span className="text-foreground">{background.panel_selection_rationale}</span>
        </p>
      ) : null}
      {background.taxonomy_resolution_status ? (
        <p className="mt-1">
          Taxonomy: FASTA labels are not resolved or validated by this scan. User-declared
          provenance is retained but not independently verified; population-frequency coverage is
          not computed and ongoing sequence surveillance remains external.
        </p>
      ) : null}
      {background.topology_note ? (
        <p className="mt-1">Topology: {background.topology_note}</p>
      ) : null}
    </div>
  );
}

/**
 * Where one design's oligos have sequence-compatible alternative windows.
 *
 * Sites and opposing-site products are reported separately. This bounded
 * sequence model does not prove polymerase extension or an observed band; it
 * identifies geometries that cannot be dismissed from the supplied sequence
 * alone and therefore need downstream specificity evidence.
 */
export function ScanFindings({
  off,
  /** What the design is meant to produce, so "extra" is countable. */
  intended = 0,
}: {
  off: OffTargets | undefined;
  intended?: number;
}) {
  if (!off?.checked) return null;

  const products = off.products ?? [];
  const sites = off.site_count ?? 0;
  const extra = Math.max(sites - intended, 0);

  if (products.length === 0) {
    return (
      <p className="text-xs leading-relaxed text-muted-foreground">
        {extra > 0
          ? `No opposing-site product under this bounded sequence model. ${count(extra)} extra sequence-compatible site(s) remain; they do not form a modeled left/right product here and still require context-appropriate validation.`
          : "No second sequence-compatible site was found within the supplied background and mismatch envelope."}
      </p>
    );
  }

  return (
    <details>
      <summary className="min-h-6 cursor-pointer py-1 text-xs text-muted-foreground hover:text-foreground">
        Sequence-possible off-target products ({off.product_count ?? products.length})
      </summary>
      <ul className="mt-2 space-y-1">
        {products.map((product) => (
          <li
            key={`${product.contig}:${product.start}:${product.size}`}
            className="flex flex-wrap gap-x-3 text-xs text-muted-foreground"
          >
            <span className="text-foreground tabular-nums">{product.size} bp</span>
            <span className="truncate">
              {product.contig}:{count(product.start)}–{count(product.end)}
            </span>
            <span className="tabular-nums">weaker primer binds at {product.worst_dg} kcal/mol</span>
          </li>
        ))}
      </ul>
    </details>
  );
}

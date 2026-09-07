import type { MultiplexRequest } from "@/lib/api/transport";

function field(form: FormData, name: string): string {
  const value = form.get(name);
  return typeof value === "string" ? value.trim() : "";
}

function optionalNumber(form: FormData, name: string): number | undefined {
  const raw = field(form, name);
  if (!raw) return undefined;
  const value = Number(raw);
  if (!Number.isFinite(value)) {
    throw new Error(`${name} must be a finite number.`);
  }
  return value;
}

/**
 * Every target a multiplex form sent, in index order.
 *
 * Rows travel as `target_${index}_*`. The form compacts the indices before it
 * serialises, but older payloads were written with gaps — removing the first
 * row used to leave rows numbered 1 and 2 behind a missing 0. So this reads
 * every matching key and sorts numerically rather than walking upward and
 * stopping at the first absence: stopping there once turned a removed first
 * row into a form that could not be submitted at all.
 */
export function collectTargets(form: FormData): MultiplexRequest["targets"] {
  const indices = [...form.keys()]
    .flatMap((key) => {
      const found = /^target_(\d+)_template$/.exec(key);
      return found && field(form, key) ? [Number(found[1])] : [];
    })
    .sort((left, right) => left - right);

  return indices.map((index) => {
    const min = optionalNumber(form, `target_${index}_min`);
    const max = optionalNumber(form, `target_${index}_max`);
    const constraints: Record<string, number> = {};
    // These names cross into the shared flanking-pair worker. The UI names
    // describe a product size, but `Constraints` publishes `product_min` and
    // `product_max`; sending the former made an entered value fail as an
    // unknown constraint instead of reaching Primer3.
    if (min !== undefined) constraints.product_min = min;
    if (max !== undefined) constraints.product_max = max;

    return {
      name: field(form, `target_${index}_name`) || `Target ${index + 1}`,
      template: field(form, `target_${index}_template`),
      background: field(form, `target_${index}_background`) || undefined,
      inclusivity: field(form, `target_${index}_inclusivity`) || undefined,
      inclusivityPanelProvenance:
        field(form, `target_${index}_inclusivity_panel_provenance`) || undefined,
      backgroundPanelProvenance:
        field(form, `target_${index}_background_panel_provenance`) || undefined,
      speciesPanelSelectionRationale:
        field(form, `target_${index}_species_panel_selection_rationale`) || undefined,
      speciesTargetTaxid: optionalNumber(form, `target_${index}_species_target_taxid`),
      speciesTaxonomySnapshot:
        field(form, `target_${index}_species_taxonomy_snapshot`) || undefined,
      speciesDatabaseSnapshot:
        field(form, `target_${index}_species_database_snapshot`) || undefined,
      speciesPanelAccessionManifest:
        field(form, `target_${index}_species_panel_accession_manifest`) || undefined,
      speciesPanelRecordMetadataManifest:
        field(form, `target_${index}_species_panel_record_metadata_manifest`) || undefined,
      speciesPanelRetrievedDate:
        field(form, `target_${index}_species_panel_retrieved_date`) || undefined,
      tube: field(form, `target_${index}_tube`) || undefined,
      primerConcentrationNm: optionalNumber(form, `target_${index}_primer_concentration_nm`),
      empiricalEvidenceRef: field(form, `target_${index}_empirical_evidence_ref`) || undefined,
      constraints: Object.keys(constraints).length ? constraints : undefined,
    };
  });
}

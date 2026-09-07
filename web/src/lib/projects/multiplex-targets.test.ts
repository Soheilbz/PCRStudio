import { describe, expect, it } from "vitest";

import { collectTargets } from "./multiplex-targets";

function formWith(rows: Record<string, string>): FormData {
  const form = new FormData();
  for (const [key, value] of Object.entries(rows)) form.set(key, value);
  return form;
}

describe("collectTargets", () => {
  it("reads compact rows in order", () => {
    const targets = collectTargets(
      formWith({
        target_0_template: "ACGT",
        target_0_name: "first",
        target_1_template: "TGCA",
        target_1_name: "second",
      }),
    );

    expect(targets).toHaveLength(2);
    expect(targets[0]).toMatchObject({ name: "first", template: "ACGT" });
    expect(targets[1]).toMatchObject({ name: "second", template: "TGCA" });
  });

  it("still reads the rows behind a removed first row", () => {
    // Serialised by the form as it was before the indices were compacted:
    // removing the first row left a gap at 0, and a collector that stopped
    // there read nothing at all.
    const targets = collectTargets(
      formWith({
        target_1_template: "TGCA",
        target_1_name: "second",
        target_2_template: "GGCC",
        target_2_min: "150",
        target_2_max: "300",
      }),
    );

    expect(targets).toHaveLength(2);
    expect(targets[0]).toMatchObject({ name: "second", template: "TGCA" });
    expect(targets[1]?.name).toBe("Target 3");
    expect(targets[1]?.constraints).toEqual({ product_min: 150, product_max: 300 });
  });

  it("carries a target's exclusion background without dropping it", () => {
    const targets = collectTargets(
      formWith({
        target_0_template: "ACGT",
        target_0_background: ">relative\nTGCA",
      }),
    );

    expect(targets[0]?.background).toBe(">relative\nTGCA");
  });

  it("carries species-panel provenance and selection rationale without dropping them", () => {
    const targets = collectTargets(
      formWith({
        target_0_template: "ACGT",
        target_0_inclusivity_panel_provenance: "RefSeq release X; A.1",
        target_0_background_panel_provenance: "RefSeq release X; B.1",
        target_0_species_panel_selection_rationale: "target diversity and nearest neighbours",
        target_0_species_target_taxid: "562",
        target_0_species_taxonomy_snapshot: "NCBI Taxonomy snapshot 2026-09-04",
        target_0_species_database_snapshot: "RefSeq genomes release 232",
        target_0_species_panel_accession_manifest: "GCF_000005845.2\nGCF_000008865.2",
        target_0_species_panel_record_metadata_manifest:
          "strain-a\tGCF_000005845.2\tinclusivity\tlinear\nrelative\tGCF_000008865.2\texclusivity\tlinear",
        target_0_species_panel_retrieved_date: "2026-09-04",
      }),
    );

    expect(targets[0]).toMatchObject({
      inclusivityPanelProvenance: "RefSeq release X; A.1",
      backgroundPanelProvenance: "RefSeq release X; B.1",
      speciesPanelSelectionRationale: "target diversity and nearest neighbours",
      speciesTargetTaxid: 562,
      speciesTaxonomySnapshot: "NCBI Taxonomy snapshot 2026-09-04",
      speciesDatabaseSnapshot: "RefSeq genomes release 232",
      speciesPanelAccessionManifest: "GCF_000005845.2\nGCF_000008865.2",
      speciesPanelRecordMetadataManifest:
        "strain-a\tGCF_000005845.2\tinclusivity\tlinear\nrelative\tGCF_000008865.2\texclusivity\tlinear",
      speciesPanelRetrievedDate: "2026-09-04",
    });
  });

  it("skips an empty template rather than submitting a blank tube", () => {
    const targets = collectTargets(
      formWith({
        target_0_template: "   ",
        target_1_template: "TGCA",
      }),
    );

    expect(targets).toHaveLength(1);
    expect(targets[0]?.template).toBe("TGCA");
  });

  it("names an unnamed target from its position", () => {
    const targets = collectTargets(formWith({ target_0_template: "ACGT" }));
    expect(targets[0]?.name).toBe("Target 1");
  });
});

it("rejects malformed numeric target constraints instead of silently dropping them", () => {
  const form = new FormData();
  form.set("target_0_template", "ACGT");
  form.set("target_0_min", "not-a-number");
  expect(() => collectTargets(form)).toThrow(/target_0_min must be a finite number/);
});

import { describe, expect, it } from "vitest";

import { forkSettingsFromRequest } from "./fork-settings";

describe("forkSettingsFromRequest", () => {
  it("restores common values and converts zero-based coordinates", () => {
    expect(
      forkSettingsFromRequest(
        {
          template: "ACGT",
          polymerase: "taq",
          background: ">relative\nTTTT",
          inclusivity: ">strain-a\nACGT",
          inclusivityPanelProvenance: "RefSeq release X; A.1",
          backgroundPanelProvenance: "RefSeq release X; B.1",
          speciesPanelSelectionRationale: "target diversity and closest neighbours",
          speciesTargetTaxid: 562,
          speciesTaxonomySnapshot: "NCBI Taxonomy snapshot 2026-09-04",
          speciesDatabaseSnapshot: "RefSeq genomes release 232",
          speciesPanelAccessionManifest: "GCF_000005845.2\nGCF_000008865.2",
          speciesPanelRecordMetadataManifest:
            "strain-a\tGCF_000005845.2\tinclusivity\tlinear\nrelative\tGCF_000008865.2\texclusivity\tlinear",
          speciesPanelRetrievedDate: "2026-09-04",
          targetStart: 9,
          targetLength: 80,
          excluded: [
            [0, 4],
            [20, 2],
          ],
          variants: [2, 10],
          constraints: { product_min: 100 },
        },
        "target",
      ),
    ).toMatchObject({
      name: "target",
      template: "ACGT",
      background: ">relative\nTTTT",
      inclusivity: ">strain-a\nACGT",
      inclusivityPanelProvenance: "RefSeq release X; A.1",
      backgroundPanelProvenance: "RefSeq release X; B.1",
      speciesPanelSelectionRationale: "target diversity and closest neighbours",
      speciesTargetTaxid: "562",
      speciesTaxonomySnapshot: "NCBI Taxonomy snapshot 2026-09-04",
      speciesDatabaseSnapshot: "RefSeq genomes release 232",
      speciesPanelAccessionManifest: "GCF_000005845.2\nGCF_000008865.2",
      speciesPanelRecordMetadataManifest:
        "strain-a\tGCF_000005845.2\tinclusivity\tlinear\nrelative\tGCF_000008865.2\texclusivity\tlinear",
      speciesPanelRetrievedDate: "2026-09-04",
      targetStart: "10",
      targetLength: "80",
      avoided: "1-4,21-22",
      variants: "3,11",
      c_product_min: "100",
    });
  });

  it("restores engine-specific nested, probe, edit, assembly, and tail fields", () => {
    expect(
      forkSettingsFromRequest({
        outer: { product_min: 100 },
        inner: { product_max: 250 },
        probe: { tm_min: 66 },
        shares: "forward",
        margin: 12,
        singleTube: true,
        sequencingProtocol: "bigdye-v3-1",
        sequencingInstrument: "3730xl",
        sequencingFacilitySop: "facility-SOP-7",
        probeProtocol: "taqman-mgb",
        raceDirection: "5prime",
        raceAdapter: "generacer-kit-25-0355-vl",
        postAmplificationProtocol: "neb-q5-e0554",
        edit: { kind: "substitution", at: 4, to: "G", replacing: 1 },
        alleles: ["A", "G"],
        segments: [{ name: "insert", kind: "template", sequence: "ACGT" }],
        tails: {
          forward: "ADAPTER",
          reverse: "TAIL",
        },
        vectorPrimer: { name: "VP", sequence: "GG", readsInto: "insert", vector: "TT" },
        windows: { outer: { tm_min: 58 }, f2_b2_span: [120, 170] },
      }),
    ).toEqual({
      outer_product_min: "100",
      inner_product_max: "250",
      probe_tm_min: "66",
      shares: "forward",
      margin: "12",
      singleTube: "true",
      sequencingProtocol: "bigdye-v3-1",
      sequencingInstrument: "3730xl",
      sequencingFacilitySop: "facility-SOP-7",
      probeProtocol: "taqman-mgb",
      raceDirection: "5prime",
      raceAdapter: "generacer-kit-25-0355-vl",
      postAmplificationProtocol: "neb-q5-e0554",
      editKind: "substitution",
      editAt: "5",
      editTo: "G",
      editReplacing: "1",
      alleleOne: "A",
      alleleTwo: "G",
      segments: "insert,template,ACGT",
      tailForward: "ADAPTER",
      tailReverse: "TAIL",
      vectorPrimerName: "VP",
      vectorPrimerSequence: "GG",
      vectorPrimerReadsInto: "insert",
      vectorSequence: "TT",
      w_outer_tm_min: "58",
      w_f2_b2_span_min: "120",
      w_f2_b2_span_max: "170",
      variantType: "snv",
      variantRef: "A",
      variantAlt: "G",
    });
  });

  it("restores the named sequencing chemistry overlay", () => {
    expect(forkSettingsFromRequest({ sequencingProtocol: "bigdye-v3-1" })).toEqual({
      sequencingProtocol: "bigdye-v3-1",
    });
  });

  it("restores the named Standard-PCR chemistry overlay", () => {
    expect(forkSettingsFromRequest({ standardPcrProtocol: "neb-q5-hot-start-m0493" })).toEqual({
      standardPcrProtocol: "neb-q5-hot-start-m0493",
    });
  });

  it("restores the named SYBR chemistry overlay", () => {
    expect(forkSettingsFromRequest({ qpcrProtocol: "bio-rad-itaq-sybr" })).toEqual({
      qpcrProtocol: "bio-rad-itaq-sybr",
    });
  });

  it("restores the named RPA chemistry overlay", () => {
    expect(forkSettingsFromRequest({ rpaProtocol: "twistamp-basic" })).toEqual({
      rpaProtocol: "twistamp-basic",
    });
  });

  it("restores the named digital PCR chemistry overlay", () => {
    expect(forkSettingsFromRequest({ digitalProtocol: "bio-rad-qx200-evagreen" })).toEqual({
      digitalProtocol: "bio-rad-qx200-evagreen",
    });
  });

  it("restores digital PCR run-handoff provenance", () => {
    expect(
      forkSettingsFromRequest({
        digitalPartitionFormat: "droplet",
        digitalPlatformId: "bio-rad-qx200",
        digitalPlatformName: "Bio-Rad QX200",
        digitalFragmentationState: "not-assessed",
      }),
    ).toEqual({
      digitalPartitionFormat: "droplet",
      digitalPlatformId: "bio-rad-qx200",
      digitalPlatformName: "Bio-Rad QX200",
      digitalFragmentationState: "not-assessed",
    });
  });

  it("restores sequencing instrument handoff", () => {
    expect(
      forkSettingsFromRequest({
        sequencingInstrument: "3730xl",
        sequencingFacilitySop: "facility-SOP-7",
      }),
    ).toEqual({
      sequencingInstrument: "3730xl",
      sequencingFacilitySop: "facility-SOP-7",
    });
  });
  it("restores LAMP readout and preprocessing decisions", () => {
    expect(
      forkSettingsFromRequest({
        lampProtocol: "neb-e1708",
        lampReadout: "fluorescence",
        lowercaseMasking: false,
      }),
    ).toEqual({
      lampProtocol: "neb-e1708",
      lampReadout: "fluorescence",
      lowercaseMasking: "false",
    });
  });

  it("restores the complete LAMP scenario, numeric context, and source-bounded optimization contract", () => {
    expect(
      forkSettingsFromRequest({
        fromRna: false,
        lampProtocol: "meridian-mdx126",
        lampReadout: "fluorescence",
        lampReadoutChemistry: "syto82",
        lampSampleMatrix: "blood-plasma-serum",
        lampSamplePreparation: "direct-addition",
        lampFormulation: "air-dryable",
        lampConfirmationMode: "sequence-confirmation",
        lampDetectionTopology: "nonspecific-dsdna",
        lampDesignIntent: "standard",
        lampLoopPolicy: "require-six",
        lampCarryoverStrategy: "protocol-default",
        lampReconstitutionX: "protocol-default",
        lampSpecificityAdditive: "none",
        lampAccelerationAdditive: "none",
        lampPrimerKineticsProfile: "protocol-default",
        lampPreincubationStrategy: "protocol-default",
        lampSampleBufferType: "water",
        lampInstrumentProfile: "other-validated",
        lampSampleInputPercent: 10,
        lampSampleBufferPh: 7.5,
        lampSampleBufferPercent: 5,
        lampTransportMediumPercent: 10,
        lampBileSaltMgMl: 1,
        lampCaryBlairPercent: 10,
        lampUpstreamGuanidineMm: 20,
        lampBenchOptimization: {
          magnesium_mM: 8,
          fip_bip_uM: 1.6,
          loop_uM: 0.8,
        },
      }),
    ).toMatchObject({
      fromRna: "false",
      lampProtocol: "meridian-mdx126",
      lampReadout: "fluorescence",
      lampReadoutChemistry: "syto82",
      lampSampleMatrix: "blood-plasma-serum",
      lampSamplePreparation: "direct-addition",
      lampFormulation: "air-dryable",
      lampConfirmationMode: "sequence-confirmation",
      lampDetectionTopology: "nonspecific-dsdna",
      lampDesignIntent: "standard",
      lampLoopPolicy: "require-six",
      lampCarryoverStrategy: "protocol-default",
      lampReconstitutionX: "protocol-default",
      lampSpecificityAdditive: "none",
      lampAccelerationAdditive: "none",
      lampPrimerKineticsProfile: "protocol-default",
      lampPreincubationStrategy: "protocol-default",
      lampSampleBufferType: "water",
      lampInstrumentProfile: "other-validated",
      lampSampleInputPercent: "10",
      lampSampleBufferPh: "7.5",
      lampSampleBufferPercent: "5",
      lampTransportMediumPercent: "10",
      lampBileSaltMgMl: "1",
      lampCaryBlairPercent: "10",
      lampUpstreamGuanidineMm: "20",
      lampOptMagnesium: "8",
      lampOptFipBip: "1.6",
      lampOptLoop: "0.8",
    });
  });

  it("restores Flanking numeric, colony, and restriction-workflow context without flattening authority", () => {
    expect(
      forkSettingsFromRequest({
        colonyHostClass: "bacterial",
        colonyPreparation: "direct-transfer",
        colonyProtocolId: "neb-onetaq-hotstart-m0488-colony",
        restrictionDigestProtocol: "neb-cutsmart-standard",
        restrictionDephosphorylationProtocol: "neb-quick-cip-m0525",
        restrictionLigationProtocol: "neb-quick-ligation-m2200",
        flankingNumericContext: {
          reactionVolumeUl: 50,
          primerEachUm: 0.2,
          initialDenaturationTimeMin: 3,
          preparation: "direct-transfer",
        },
      }),
    ).toMatchObject({
      colonyHostClass: "bacterial",
      colonyPreparation: "direct-transfer",
      colonyProtocolId: "neb-onetaq-hotstart-m0488-colony",
      restrictionDigestProtocol: "neb-cutsmart-standard",
      restrictionDephosphorylationProtocol: "neb-quick-cip-m0525",
      restrictionLigationProtocol: "neb-quick-ligation-m2200",
      flankingReactionVolumeUl: "50",
      flankingPrimerEachUm: "0.2",
      colonyInitialDenaturationMin: "3",
    });
  });

  it("restores RPA numeric and optional PowerTrack-style additive context without losing booleans", () => {
    expect(
      forkSettingsFromRequest({
        flankingNumericContext: {
          primerEachNm: 150,
          additive: "yellow-sample-buffer",
          rpaTemperatureC: 40,
          rpaTimeMin: 25,
          rpaBstUnitsPerUl: 0.05,
          rpaMultiplex: true,
        },
      }),
    ).toMatchObject({
      flankingPrimerEachNm: "150",
      flankingAdditive: "yellow-sample-buffer",
      rpaTemperatureC: "40",
      rpaTimeMin: "25",
      rpaBstUnitsPerUl: "0.05",
      rpaMultiplex: "true",
    });
  });

  it("restores transcript-junction annotations without shifting their boundary frame", () => {
    expect(forkSettingsFromRequest({ exonJunctions: [450, 812] })).toEqual({
      exonJunctions: "450,812",
    });
  });

  it("restores tiled-scheme lifecycle inputs and alignment authority", () => {
    expect(
      forkSettingsFromRequest({
        alignmentMode: "prealigned",
        tilingOperation: "repair-mode",
        tilingAlignmentMode: "prealigned",
        existingBed: "ref\t0\t100\tprimer_LEFT\t1\t+",
        schemeConfig: '{"scheme":1}',
        regionBed: "ref\t10\t80",
        panelMode: "region-only",
        primerName: "primer_1",
      }),
    ).toEqual({
      alignmentMode: "prealigned",
      tilingOperation: "repair-mode",
      tilingAlignmentMode: "prealigned",
      existingBed: "ref\t0\t100\tprimer_LEFT\t1\t+",
      schemeConfig: '{"scheme":1}',
      regionBed: "ref\t10\t80",
      panelMode: "region-only",
      primerName: "primer_1",
    });
  });

  it("restores restriction-tail protocol identity with the tail geometry", () => {
    expect(
      forkSettingsFromRequest({
        tails: {
          tailProtocol: "neb-general-6bp",
          forwardEnzyme: "EcoRI",
          reverseEnzyme: "BamHI",
          protectiveBases: 6,
        },
      }),
    ).toEqual({
      tailProtocol: "neb-general-6bp",
      forwardEnzyme: "EcoRI",
      reverseEnzyme: "BamHI",
      protectiveBases: "6",
    });
  });

  it("restores numeric specificity and genotyping settings", () => {
    expect(
      forkSettingsFromRequest({ maxMismatches: 4, tetraMinBandSeparationBp: 60 }),
    ).toMatchObject({
      maxMismatches: "4",
      tetraMinBandSeparationBp: "60",
    });
  });

  it("round-trips all current engine scientific settings without object-string corruption", () => {
    const restored = forkSettingsFromRequest({
      probeProtocol: "idt-primetime-conventional",
      probeChemistry: "double-quenched-hydrolysis",
      probeReporter: "FAM",
      probeQuencher: "IABkFQ",
      probeInternalQuencher: "ZEN",
      probeInstrumentProfile: "quantstudio-5",
      probeTranscriptMode: "exon-junction",
      probeMultiplexPanel: [{ target: "geneA", reporter: "FAM", quencher: "IABkFQ" }],
      raceChemistry: "firstchoice-rlm-race",
      sequencingDesignProfile: "azenta-genewiz",
      sequencingProvider: "azenta-genewiz",
      sequencingUniversalPrimerScan: true,
      sequencingBidirectional: true,
      enzymeCohortSize: 3,
      mappingUseCase: "transposon-insertion",
      tilingBackend: "olivar",
      tilingMinBaseFrequency: 0.01,
      tilingBacktrack: true,
      tilingHighGc: false,
      olivarSeed: 10,
      olivarDegenerateMode: true,
      olivarCheckVariants: true,
      schemeVersion: "v1.2.0",
      tilingTargets: [{ id: "segment-a", sequence: "ACGT" }],
    });

    expect(restored).toMatchObject({
      probeChemistry: "double-quenched-hydrolysis",
      probeReporter: "FAM",
      probeQuencher: "IABkFQ",
      probeInternalQuencher: "ZEN",
      probeInstrumentProfile: "quantstudio-5",
      probeTranscriptMode: "exon-junction",
      raceChemistry: "firstchoice-rlm-race",
      sequencingDesignProfile: "azenta-genewiz",
      sequencingProvider: "azenta-genewiz",
      sequencingUniversalPrimerScan: "true",
      sequencingBidirectional: "true",
      enzymeCohortSize: "3",
      mappingUseCase: "transposon-insertion",
      tilingBackend: "olivar",
      tilingMinBaseFrequency: "0.01",
      tilingBacktrack: "true",
      tilingHighGc: "false",
      olivarSeed: "10",
      olivarDegenerateMode: "true",
      olivarCheckVariants: "true",
      schemeVersion: "v1.2.0",
    });
    expect(JSON.parse(restored.probeMultiplexPanel!)).toEqual([
      { target: "geneA", reporter: "FAM", quencher: "IABkFQ" },
    ]);
    expect(JSON.parse(restored.tilingTargets!)).toEqual([{ id: "segment-a", sequence: "ACGT" }]);
    expect(restored.probeMultiplexPanel).not.toContain("[object Object]");
    expect(restored.tilingTargets).not.toContain("[object Object]");
  });
});

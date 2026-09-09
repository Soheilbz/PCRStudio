/**
 * What each assay's form sends, against what its engine accepts.
 *
 * Every engine sets `deny_unknown_fields`, deliberately: a misspelt parameter
 * that is silently ignored produces a run whose settings are not the settings
 * somebody asked for. The cost of that strictness is that a form sending one
 * field too many does not degrade — it fails.
 *
 * Three assays did exactly that, and none was visible from either side alone.
 * Nested PCR has two round-specific windows, but still accepts the shared
 * background and avoided-region fields. Universal primers had no branch at all
 * and fell through to the amplification shape, sending five fields it refuses.
 * LAMP carried a constraint block its engine has no field for. These contracts
 * are checked against the request structs below so comments cannot become the
 * only source of truth again.
 *
 * The request builder is called here rather than read: an earlier version of
 * this file parsed `actions.ts` with a regular expression, and the parser was
 * wrong twice — once silently, reporting one branch's fields as another's. A
 * test that reads the wrong code is worse than no test.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { ENGINE_IDS } from "@/lib/contracts/module-bindings.generated";
import { requestFor } from "./request";

const ENGINES = resolve(process.cwd(), "../crates/pcr-core/src/engines");

/** The fields one engine's own request struct declares, in wire spelling. */
function accepts(engine: string): Set<string> {
  // The struct is named after the engine with the words joined, so it is
  // derived rather than listed — a twelfth engine needs no edit here.
  const stem = engine.split("-").join("_");
  const wanted = `${stem
    .split("_")
    .map((word) => word[0]!.toUpperCase() + word.slice(1))
    .join("")}Request`;

  // Line endings normalised: this fixture deliberately carries legacy CRLF input.
  const source = readFileSync(resolve(ENGINES, `${stem}.rs`), "utf8")
    .split("\r\n")
    .join("\n");

  const opener = `pub struct ${wanted} {`;
  const from = source.indexOf(opener);
  if (from < 0) throw new Error(`no ${wanted} in ${stem}.rs`);

  const block = source.slice(from + opener.length, source.indexOf("\n}", from));

  // Rust is snake_case and the wire is camelCase, via serde's `rename_all`.
  return new Set(
    [...block.matchAll(/\bpub (\w+):/g)].map(([, name]) =>
      name!.replace(/_(\w)/g, (_, letter: string) => letter.toUpperCase()),
    ),
  );
}

/**
 * A form with every control filled in.
 *
 * Every one, deliberately. A field left empty is dropped on the way out, so a
 * form that only fills in what an assay shows would prove nothing: the bug
 * being guarded against is a value that survives in a draft — from a step that
 * was removed, or a module the project was started under — and is sent to an
 * engine with no field for it.
 */
function everything(): FormData {
  const form = new FormData();
  const filled: Record<string, string> = {
    name: "check",
    moduleId: "species-specific-pcr",
    polymerase: "taq-standard",
    purpose: "general",
    background: ">bg\nACGTACGTACGTACGT",
    inclusivity: ">strain-a\nACGTACGTACGTACGT",
    inclusivityPanelProvenance: "RefSeq release X; accession A.1",
    backgroundPanelProvenance: "RefSeq release X; accession B.1",
    speciesPanelSelectionRationale: "target diversity and nearest neighbours",
    speciesTargetTaxid: "562",
    speciesTaxonomySnapshot: "NCBI Taxonomy snapshot 2026-09-04",
    speciesDatabaseSnapshot: "RefSeq genomes release 232",
    speciesPanelAccessionManifest: "GCF_000005845.2\nGCF_000008865.2",
    speciesPanelRecordMetadataManifest:
      "strain-a\tGCF_000005845.2\tinclusivity\tlinear\nbg\tGCF_000008865.2\texclusivity\tlinear",
    speciesPanelRetrievedDate: "2026-09-04",
    maxMismatches: "3",
    howMany: "5",
    targetStart: "100",
    targetLength: "50",
    avoided: "10-20",
    // Constraints travel by prefix. Anonymous chemistry overrides are not a current UI surface.
    c_tm_min: "58",
    c_product_max: "400",
    // Everything an engine-specific card can carry.
    parameterSet: "standard",
    lampProtocol: "neb-e1700",
    lampReadout: "fluorescence",
    lampReadoutChemistry: "syto9",
    lampSampleMatrix: "purified-nucleic-acid",
    lampSamplePreparation: "purified",
    lampFormulation: "liquid",
    lampConfirmationMode: "none",
    lampDetectionTopology: "nonspecific-dsdna",
    lampDesignIntent: "standard",
    lampLoopPolicy: "prefer-six",
    lampCarryoverStrategy: "protocol-default",
    lampReconstitutionX: "protocol-default",
    lampSpecificityAdditive: "none",
    lampAccelerationAdditive: "none",
    lampPrimerKineticsProfile: "protocol-default",
    lampPreincubationStrategy: "protocol-default",
    lampSampleBufferType: "none",
    lampInstrumentProfile: "not-specified",
    lampSampleInputPercent: "10",
    lampSampleBufferPh: "7.5",
    lampSampleBufferPercent: "5",
    lampTransportMediumPercent: "10",
    lampBileSaltMgMl: "1",
    lampCaryBlairPercent: "10",
    lampUpstreamGuanidineMm: "20",
    lampOptMagnesium: "8",
    lampOptDntpEach: "1.4",
    lampOptBetaine: "0.8",
    lampOptPolymeraseUnits: "8",
    lampOptRtUnits: "7.5",
    lampOptFipBip: "1.6",
    lampOptF3B3: "0.2",
    lampOptLoop: "0.8",
    lampOptTemperature: "65",
    lampOptTime: "30",
    lampOptGuanidine: "40",
    lampOptDyeX: "1",
    lampGeometryProfile: "pcrstudio-evidence-2026",
    lampInnerLinker: "tttt",
    longRangeProtocol: "thermo-long-pcr-k018x",
    colonyHostClass: "bacterial",
    colonyPreparation: "direct-transfer",
    colonyProtocolId: "custom-sop",
    colonyProtocolName: "validated-colony-SOP",
    colonyProtocolProvenance: "lab QA system / SOP rev A / 2026-08-01",
    circleLength: "2686",
    enzyme: "EcoRI",
    inverseBranch: "restriction-self-ligation",
    leftEndPhosphate: "unresolved",
    rightEndPhosphate: "unresolved",
    circularizationProvenance: "unresolved",
    linearControlProvenance: "unresolved",
    methylationBranch: "unresolved",
    at: "250",
    alleleOne: "A",
    alleleTwo: "G",
    geometry: "kasp",
    kaspProtocol: "lgc-standard",
    kaspAssayMode: "biallelic-genotype",
    kaspPlateFormat: "96",
    kaspInstrumentModel: "unresolved",
    kaspRoxPolicy: "unresolved",
    tetraMinBandSeparationBp: "40",
    probeProtocol: "taqman-mgb",
    rpaProtocol: "twistamp-basic",
    digitalProtocol: "bio-rad-qx200-evagreen",
    digitalPartitionFormat: "droplet",
    digitalPlatformId: "bio-rad-qx200",
    digitalPlatformName: "Bio-Rad QX200",
    digitalFragmentationState: "not-assessed",
    editKind: "substitute",
    editAt: "300",
    editTo: "T",
    editReplacing: "1",
    direction: "forward",
    raceDirection: "5prime",
    raceAdapter: "generacer-kit-25-0355-vl",
    raceSubstrate: "total-rna",
    racePreparation: "GeneRacer Kit 25-0355 Version L",
    raceRound: "primary",
    deadZone: "40",
    readLength: "700",
    overlap: "75",
    slide: "20",
    pools: "2",
    segments: "insert,amplified,ACGTACGTACGT",
    circular: "true",
    method: "gibson",
    assemblyProtocol: "neb-e5510",
    postAmplificationProtocol: "neb-q5-e0554",
    alignmentMode: "auto",
    tilingOperation: "scheme-create",
    tilingAlignmentMode: "auto",
    outer_tm_min: "57",
    inner_tm_min: "57",
    shares: "nothing",
    margin: "30",
    singleTube: "false",
    carryoverPrevention: "not-selected",
    forwardEnzyme: "EcoRI",
    reverseEnzyme: "BamHI",
    protectiveBases: "6",
    forwardProtectiveSequence: "GACTTA",
    reverseProtectiveSequence: "CAGTTA",
    restrictionDigestProtocol: "neb-cutsmart-standard",
    restrictionDephosphorylationProtocol: "none",
    restrictionLigationProtocol: "neb-t4-dna-ligase-m0202",
    vectorPrimerName: "M13 forward",
    vectorPrimerReadsInto: "start",
    // Sent by the eight assays that declare the reverse-transcription
    // modifier; several engines carry it. Filled here so this test would fail if a
    // sixth branch started spreading it.
    fromRna: "true",
    exonJunctions: "450, 812",
  };
  for (const [key, value] of Object.entries(filled)) form.set(key, value);
  return form;
}

/** Every canonical engine, generated from contracts/engines.toml. */
describe("no form sends a field its engine refuses", () => {
  it("found the engines to check", () => {
    // The failure mode of a test like this is an empty list that passes.
    expect(ENGINE_IDS).toHaveLength(11);
    expect(ENGINE_IDS).toContain("flanking-pair");
  });

  it.each(ENGINE_IDS)("%s", (engine) => {
    const built = requestFor(engine, ">t\nACGTACGTACGTACGTACGT", everything());

    // `undefined` fields never reach the wire — JSON drops them — so only what
    // is actually set counts as sent.
    const sent = Object.entries(built)
      .filter(([, value]) => value !== undefined)
      .map(([key]) => key);

    const allowed = accepts(engine);
    const refused = sent.filter((name) => !allowed.has(name)).sort();

    expect(refused, `these turn a valid run into "unknown field"`).toEqual([]);
  });

  it("still sends what each engine does need", () => {
    // The other way this could pass: a builder that sends nothing at all.
    const of = (engine: string) =>
      new Set(
        Object.entries(requestFor(engine, ">t\nACGT", everything()))
          .filter(([, value]) => value !== undefined)
          .map(([key]) => key),
      );

    expect(of("flanking-pair")).toContain("targetStart");
    expect(of("flanking-pair")).toContain("background");
    expect(of("flanking-pair")).toContain("maxMismatches");
    expect(of("loop-set")).toContain("parameterSet");
    expect(of("loop-set")).toContain("lampProtocol");
    for (const field of [
      "lampReadout",
      "lampReadoutChemistry",
      "lampSampleMatrix",
      "lampSamplePreparation",
      "lampFormulation",
      "lampConfirmationMode",
      "lampDetectionTopology",
      "lampDesignIntent",
      "lampLoopPolicy",
      "lampBenchOptimization",
    ]) {
      expect(of("loop-set")).toContain(field);
    }
    expect(of("outward-pair")).toContain("inverseBranch");
    expect(of("outward-pair")).toContain("enzyme");
    expect(of("outward-pair")).toContain("leftEndPhosphate");
    expect(of("discriminating-pair")).toContain("alleles");
    expect(of("discriminating-pair")).toContain("kaspProtocol");
    expect(of("tiling-scheme")).toContain("overlap");
    expect(of("junction-primers")).toContain("segments");
    expect(of("junction-primers")).toContain("assemblyProtocol");
    expect(of("mutagenic-pair")).toContain("edit");
    expect(of("single-primer")).toContain("direction");
    expect(of("nested")).toContain("outer");
    expect(of("nested")).toContain("background");
    expect(of("nested")).toContain("excluded");
    // The one assay that exists to add restriction sites could not send them:
    // the engine has carried the field since it was written and no page filled
    // it in, so the cloning module designed bare primers.
    expect(of("flanking-pair")).toContain("tails");
    // The same for the colony screen: the field and the worker's screen were
    // both written and neither could be reached from a page.
    expect(of("flanking-pair")).toContain("vectorPrimer");
    expect(of("flanking-pair")).toContain("exonJunctions");
    const rpaForm = everything();
    rpaForm.set("moduleId", "rpa");
    expect(requestFor("flanking-pair", ">t\nACGT", rpaForm).rpaProtocol).toBe("twistamp-basic");
    expect(requestFor("flanking-pair", ">t\nACGT", everything()).exonJunctions).toEqual([450, 812]);
    expect(of("pair-and-probe")).not.toContain("exonJunctions");
    expect(of("pair-and-probe")).toContain("fromRna");
    expect(of("pair-and-probe")).toContain("probeProtocol");
    expect(of("loop-set")).toContain("fromRna");
    expect(of("loop-set")).toContain("inclusivity");
    expect(of("loop-set")).toContain("lampGeometryProfile");
    expect(of("loop-set")).toContain("lampInnerLinker");
    expect(of("consensus-pair")).toContain("fromRna");
  });

  it("does not carry a protocol overlay across an incompatible layout", () => {
    const form = everything();

    form.set("geometry", "arms-two-tube");
    expect(requestFor("discriminating-pair", ">t\nACGT", form).kaspProtocol).toBeUndefined();

    // Gibson is the only release-executable Gen-1 assembly topology. Stale
    // draft values cannot switch the route to another chemistry or strip the
    // reviewed E5510 identity.
    form.set("moduleId", "gibson-assembly");
    form.set("method", "nebuilder");
    form.set("assemblyProtocol", "not-selected");
    expect(requestFor("junction-primers", ">t\nACGT", form)).toMatchObject({
      method: "gibson",
      assemblyProtocol: "neb-e5510",
    });
  });

  it("routes the sequencing protocol only to the sequencing-primer module", () => {
    const form = new FormData();
    form.set("moduleId", "sequencing-primer");
    form.set("sequencingProtocol", "bigdye-v3-1");
    form.set("sequencingInstrument", "3730xl");
    form.set("sequencingFacilitySop", "facility-SOP-7");
    const request = requestFor("single-primer", ">t\nACGT", form);
    expect(request.sequencingProtocol).toBe("bigdye-v3-1");
    expect(request.sequencingInstrument).toBe("3730xl");
    expect(request.sequencingFacilitySop).toBe("facility-SOP-7");

    form.set("moduleId", "race");
    expect(requestFor("single-primer", ">t\nACGT", form).sequencingProtocol).toBeUndefined();
  });

  it("routes the named probe chemistry only through the pair-and-probe request", () => {
    const form = new FormData();
    form.set("probeProtocol", "taqman-mgb");
    expect(requestFor("pair-and-probe", ">t\nACGT", form).probeProtocol).toBe(
      "taqman-mgb-reference",
    );
    expect(requestFor("flanking-pair", ">t\nACGT", form).probeProtocol).toBeUndefined();
  });

  it("routes the named Standard-PCR chemistry only through the Standard-PCR module", () => {
    const form = new FormData();
    form.set("moduleId", "standard-pcr");
    form.set("standardPcrProtocol", "neb-q5-hot-start-m0493");
    expect(requestFor("flanking-pair", ">t\nACGT", form).standardPcrProtocol).toBe(
      "neb-q5-hot-start-m0493",
    );
    form.set("moduleId", "qpcr-sybr");
    expect(requestFor("flanking-pair", ">t\nACGT", form).standardPcrProtocol).toBeUndefined();
  });

  it("routes the named SYBR chemistry only through the qPCR/SYBR module", () => {
    const form = new FormData();
    form.set("moduleId", "qpcr-sybr");
    form.set("qpcrProtocol", "bio-rad-itaq-sybr");
    expect(requestFor("flanking-pair", ">t\nACGT", form).qpcrProtocol).toBe("bio-rad-itaq-sybr");
    form.set("moduleId", "standard-pcr");
    expect(requestFor("flanking-pair", ">t\nACGT", form).qpcrProtocol).toBeUndefined();
  });

  it("routes the named long-range protocol only through the long-range module", () => {
    const form = new FormData();
    form.set("moduleId", "long-range-pcr");
    form.set("longRangeProtocol", "thermo-long-pcr-k018x");
    expect(requestFor("flanking-pair", ">t\nACGT", form).longRangeProtocol).toBe(
      "thermo-long-pcr-k018x",
    );
    form.set("moduleId", "standard-pcr");
    expect(requestFor("flanking-pair", ">t\nACGT", form).longRangeProtocol).toBeUndefined();
  });

  it("routes the named RPA chemistry only through the RPA module", () => {
    const form = new FormData();
    form.set("moduleId", "rpa");
    form.set("rpaProtocol", "twistamp-basic");
    expect(requestFor("flanking-pair", ">t\nACGT", form).rpaProtocol).toBe("twistamp-basic");
    form.set("moduleId", "standard-pcr");
    expect(requestFor("flanking-pair", ">t\nACGT", form).rpaProtocol).toBeUndefined();
  });

  it("routes source-conditioned RPA numeric context without leaking it into Primer3 constraints", () => {
    const form = new FormData();
    form.set("moduleId", "rpa");
    form.set("rpaProtocol", "thermo-lyo-ready-rpa");
    form.set("flankingPrimerEachNm", "150");
    form.set("rpaTemperatureC", "40");
    form.set("rpaTimeMin", "25");
    form.set("rpaBstUnitsPerUl", "0.05");
    form.set("rpaMultiplex", "true");
    expect(requestFor("flanking-pair", ">t\nACGT", form)).toMatchObject({
      rpaProtocol: "thermo-lyo-ready-rpa",
      flankingNumericContext: {
        primerEachNm: 150,
        rpaTemperatureC: 40,
        rpaTimeMin: 25,
        rpaBstUnitsPerUl: 0.05,
        rpaMultiplex: true,
      },
    });
  });

  it("routes PowerTrack Yellow Sample Buffer only as explicit qPCR bench context", () => {
    const form = new FormData();
    form.set("moduleId", "qpcr-sybr");
    form.set("qpcrProtocol", "thermo-powertrack-sybr-a46xxx");
    form.set("qpcrCyclingProfile", "fast");
    form.set("flankingAdditive", "yellow-sample-buffer");
    expect(requestFor("flanking-pair", ">t\nACGT", form)).toMatchObject({
      flankingNumericContext: { cyclingProfile: "fast", additive: "yellow-sample-buffer" },
    });
  });

  it("preserves chemistry-specific dPCR primer units in the numeric request context", () => {
    const qx = new FormData();
    qx.set("moduleId", "digital-pcr");
    qx.set("digitalProtocol", "bio-rad-qx200-evagreen");
    qx.set("flankingPrimerEachNm", "250");
    expect(requestFor("flanking-pair", ">t\nACGT", qx).flankingNumericContext).toMatchObject({
      primerEachNm: 250,
    });

    const qiacuity = new FormData();
    qiacuity.set("moduleId", "digital-pcr");
    qiacuity.set("digitalProtocol", "qiagen-qiacuity-eg");
    qiacuity.set("flankingPrimerEachUm", "0.4");
    expect(requestFor("flanking-pair", ">t\nACGT", qiacuity).flankingNumericContext).toMatchObject({
      primerEachUm: 0.4,
    });
  });

  it("routes the named digital PCR chemistry only through the digital PCR module", () => {
    const form = new FormData();
    form.set("moduleId", "digital-pcr");
    form.set("digitalProtocol", "bio-rad-qx200-evagreen");
    form.set("digitalPartitionFormat", "droplet");
    form.set("digitalPlatformId", "bio-rad-qx200");
    form.set("digitalPlatformName", "Bio-Rad QX200");
    form.set("digitalFragmentationState", "not-assessed");
    expect(requestFor("flanking-pair", ">t\nACGT", form)).toMatchObject({
      digitalProtocol: "bio-rad-qx200-evagreen",
      digitalPartitionFormat: "droplet",
      digitalPlatformId: "bio-rad-qx200",
      digitalFragmentationState: "not-assessed",
    });
    expect(requestFor("flanking-pair", ">t\nACGT", form).digitalPlatformName).toBeUndefined();
    form.set("moduleId", "standard-pcr");
    expect(requestFor("flanking-pair", ">t\nACGT", form).digitalProtocol).toBeUndefined();
  });

  it("routes the named long-range protocol only through the long-range module", () => {
    const form = new FormData();
    form.set("moduleId", "long-range-pcr");
    form.set("longRangeProtocol", "thermo-long-pcr-k018x");
    expect(requestFor("flanking-pair", ">t\nACGT", form).longRangeProtocol).toBe(
      "thermo-long-pcr-k018x",
    );
    form.set("moduleId", "standard-pcr");
    expect(requestFor("flanking-pair", ">t\nACGT", form).longRangeProtocol).toBeUndefined();
  });

  it("routes the named RPA chemistry only through the RPA module", () => {
    const form = new FormData();
    form.set("moduleId", "rpa");
    form.set("rpaProtocol", "twistamp-basic");
    expect(requestFor("flanking-pair", ">t\nACGT", form).rpaProtocol).toBe("twistamp-basic");
    form.set("moduleId", "standard-pcr");
    expect(requestFor("flanking-pair", ">t\nACGT", form).rpaProtocol).toBeUndefined();
  });

  it("routes the kit-provided adapter only to the RACE module", () => {
    const form = new FormData();
    form.set("moduleId", "race");
    form.set("direction", "reverse");
    form.set("raceDirection", "5prime");
    form.set("raceAdapter", "generacer-kit-25-0355-vl");
    form.set("raceSubstrate", "total-rna");
    form.set("racePreparation", "RACE-SOP");
    form.set("raceRound", "primary");
    expect(requestFor("single-primer", ">t\nACGT", form)).toMatchObject({
      raceDirection: "5prime",
      raceAdapter: "generacer-kit-25-0355-vl",
      raceSubstrate: "total-rna",
      racePreparation: "RACE-SOP",
      raceRound: "primary",
    });
    expect(requestFor("single-primer", ">t\nACGT", form).direction).toBeUndefined();

    form.set("moduleId", "sequencing-primer");
    expect(requestFor("single-primer", ">t\nACGT", form).raceAdapter).toBeUndefined();
    expect(requestFor("single-primer", ">t\nACGT", form).raceDirection).toBeUndefined();
  });

  it("does not turn an invalid one-based coordinate into base one", () => {
    const form = new FormData();
    form.set("targetStart", "0");
    form.set("targetLength", "20");

    const request = requestFor("flanking-pair", "ACGTACGT", form);

    expect(request.targetStart).toBe(-1);
  });

  it("does not synthesize required scientific context from blank form state", () => {
    const blank = (moduleId: string) => {
      const form = new FormData();
      form.set("moduleId", moduleId);
      return form;
    };

    expect(requestFor("nested", ">t\nACGT", blank("nested-pcr"))).toMatchObject({
      shares: undefined,
      margin: undefined,
      carryoverPrevention: undefined,
    });
    expect(
      requestFor("consensus-pair", ">a\nACGT\n>b\nACGT", blank("universal-primers")).alignmentMode,
    ).toBeUndefined();
    expect(requestFor("tiling-scheme", ">t\nACGT", blank("tiled-scheme"))).toMatchObject({
      tilingOperation: undefined,
      tilingAlignmentMode: undefined,
    });
    expect(
      requestFor("single-primer", ">t\nACGT", blank("sequencing-primer")).direction,
    ).toBeUndefined();
    expect(requestFor("junction-primers", "", blank("gibson-assembly")).circular).toBeUndefined();

    const inverse = requestFor("outward-pair", ">t\nACGT", blank("inverse-pcr"));
    expect(inverse).toMatchObject({
      inverseBranch: undefined,
      leftEndPhosphate: undefined,
      rightEndPhosphate: undefined,
      circularizationProvenance: undefined,
      linearControlProvenance: undefined,
      methylationBranch: undefined,
    });

    const kasp = blank("kasp");
    kasp.set("geometry", "kasp");
    kasp.set("kaspProtocol", "lgc-standard");
    expect(requestFor("discriminating-pair", ">t\nACGT", kasp)).toMatchObject({
      kaspInstrumentModel: undefined,
      kaspRoxPolicy: undefined,
    });
  });

  it("does not transport removed historical draft fields into current requests", () => {
    const inverseForm = new FormData();
    inverseForm.set("moduleId", "inverse-pcr");
    inverseForm.set("enzyme", "SpeI");
    inverseForm.set("cutAt", "500");
    inverseForm.set("side", "downstream");
    inverseForm.set("r_dv_conc", "2.0");
    const inverse = requestFor("outward-pair", ">t\nACGT", inverseForm) as Record<string, unknown>;
    expect(inverse).not.toHaveProperty("cutAt");
    expect(inverse).not.toHaveProperty("side");
    expect(inverse).not.toHaveProperty("conditions");

    const cloningForm = new FormData();
    cloningForm.set("moduleId", "restriction-cloning");
    cloningForm.set("forwardEnzyme", "EcoRI");
    cloningForm.set("reverseEnzyme", "BamHI");
    cloningForm.set("forwardProtectiveBases", "3");
    cloningForm.set("reverseProtectiveBases", "8");
    const cloning = requestFor("flanking-pair", ">t\nACGT", cloningForm) as Record<string, unknown>;
    expect(cloning.tails).not.toHaveProperty("forwardProtectiveBases");
    expect(cloning.tails).not.toHaveProperty("reverseProtectiveBases");
  });

  it("does not silently drop a malformed numeric form value", () => {
    const form = new FormData();
    form.set("howMany", "not-a-number");

    expect(() => requestFor("flanking-pair", "ACGTACGT", form)).toThrow(
      "howMany must be a finite number.",
    );
  });

  it("does not silently drop a half-entered LAMP geometry range", () => {
    const form = new FormData();
    form.set("moduleId", "lamp");
    form.set("w_f2_b2_span_min", "120");

    expect(() => requestFor("loop-set", "ACGTACGT", form)).toThrow(
      "f2 b2 span requires both minimum and maximum values.",
    );
  });

  it("carries the full LAMP scenario and numeric-context contract without renaming or dropping values", () => {
    const form = new FormData();
    for (const [key, value] of Object.entries({
      moduleId: "lamp",
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
    })) {
      form.set(key, value);
    }

    expect(requestFor("loop-set", ">t\nACGTACGT", form)).toMatchObject({
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
      lampBenchOptimization: { magnesium_mM: 8, fip_bip_uM: 1.6, loop_uM: 0.8 },
      mode: "design",
    });
  });

  it("does not silently drop a malformed avoided region", () => {
    const form = new FormData();
    form.set("avoided", "10-nope");

    expect(() => requestFor("flanking-pair", "ACGTACGT", form)).toThrow(
      "avoided end must be a finite number.",
    );
  });
});

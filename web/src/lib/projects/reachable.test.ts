/**
 * Every field an engine accepts, against something on a page that fills it in.
 *
 * The other half of `wiring.test.ts`. That one refuses a form that sends a
 * field its engine has no room for; this one refuses an engine field that no
 * page can reach — a capability written, tested in the worker, and unavailable.
 *
 * Several were, and none of them was cosmetic. Restriction cloning could not
 * send the restriction sites its own engine has always accepted, so the module
 * that exists to add them ordered bare primers. Colony PCR could not name the
 * vector primer to screen against, which is the only arrangement that answers
 * the question that assay exists to ask. The probe assay could not set the
 * probe's own window, so an MGB chemistry had nowhere to say it melts ten
 * degrees higher. All of them read as finished from either side alone.
 */

import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { requestFor } from "./request";
import { draftFieldForContext } from "./required-context";

const CORE = resolve(process.cwd(), "../crates/pcr-core");
const WEB = resolve(process.cwd(), "src");
const MODULE_CONTRACTS = resolve(process.cwd(), "../knowledge/runtime/module-contracts.json");
const read = (path: string) => readFileSync(path, "utf8").split("\r\n").join("\n");

/** Every field one engine's request struct declares, in wire spelling. */
function accepts(engine: string): string[] {
  const stem = engine.split("-").join("_");
  const wanted = `${stem
    .split("_")
    .map((word) => word[0]!.toUpperCase() + word.slice(1))
    .join("")}Request`;

  const source = read(resolve(CORE, `src/engines/${stem}.rs`));
  const opener = `pub struct ${wanted} {`;
  const from = source.indexOf(opener);
  if (from < 0) throw new Error(`no ${wanted} in ${stem}.rs`);

  const block = source.slice(from + opener.length, source.indexOf("\n}", from));
  return [...block.matchAll(/\bpub (\w+):/g)].map(([, name]) =>
    name!.replace(/_(\w)/g, (_, letter: string) => letter.toUpperCase()),
  );
}

/** Which engines exist, from the file that decides which assay runs on which. */
function engines(): string[] {
  const found = new Set<string>();
  for (const line of read(resolve(CORE, "profiles.toml")).split("\n")) {
    const asEngine = /^engine = "([^"]+)"/.exec(line.trim());
    if (asEngine) found.add(asEngine[1]!);
  }
  return [...found].sort();
}

/** Public module ids grouped by the engine they actually use. */
function modulesByEngine(): Map<string, string[]> {
  const grouped = new Map<string, string[]>();
  let moduleId: string | undefined;
  for (const line of read(resolve(CORE, "profiles.toml")).split("\n")) {
    const trimmed = line.trim();
    const asId = /^id = "([^"]+)"/.exec(trimmed);
    if (asId) {
      moduleId = asId[1]!;
      continue;
    }
    const asEngine = /^engine = "([^"]+)"/.exec(trimmed);
    if (asEngine && moduleId) {
      const bucket = grouped.get(asEngine[1]!) ?? [];
      bucket.push(moduleId);
      grouped.set(asEngine[1]!, bucket);
      moduleId = undefined;
    }
  }
  return grouped;
}

/**
 * Fields no form sends, and why that is right rather than a gap.
 *
 * Every entry is a decision with a reason. Anything not listed here has to be
 * reachable, which is what makes this test worth having.
 */
const NOT_SENT: Record<string, string> = {
  assay:
    "injected by the authoritative route/profile registry rather than collected from a form; " +
    "letting the browser choose an assay payload independently of the route would weaken profile identity.",
  conditions:
    "current Scientific-Strict UI does not expose anonymous reaction-chemistry overrides; " +
    "changed chemistry requires a named/versioned profile rather than invisible draft transport.",
  modifiedOligos:
    "the current UI has no generic modified-oligo editor; chemistry-specific structured editors " +
    "own these annotations and the generic request field remains intentionally unused.",
  workflowEvidence:
    "workflow evidence is assembled from the dedicated validation/evidence step rather than a " +
    "single design control.",
  lamp: "the LAMP window family is collected by prefix (lamp_* controls), not a literal draft field.",
  probe:
    "the probe window family is collected by prefix (probe_* controls), not a literal draft field.",
  tilingTargets:
    "the current UI does not expose a free-form target-list editor; target scope is carried by " +
    "the submitted template/region controls and this optional backend field remains unused.",
};

/**
 * A form with every control on every page filled in.
 *
 * The same shape `wiring.test.ts` uses and for the mirrored reason: there, a
 * fully-filled form proves no engine receives a field it refuses; here it
 * proves every field an engine accepts is one some page can produce.
 */
function everything(moduleId: string, overrides: Record<string, string> = {}): FormData {
  const form = new FormData();
  const filled: Record<string, string> = {
    name: "check",
    moduleId,
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
    speciesPanelAccessionAuthorityManifest: "RefSeq release 232",
    maxMismatches: "3",
    howMany: "5",
    lowercaseMasking: "false",
    targetStart: "100",
    targetLength: "50",
    avoided: "10-20",
    // Positions this template is known to vary at, as somebody would type
    // them: counted from one, and inside the short fixture template above.
    variants: "3, 11",
    c_tm_min: "58",
    flankingGcEnhancerPercent: "15",
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
    probeProtocol: "thermofisher-taqman-conventional",
    probeChemistry: "conventional-hydrolysis",
    probeReporter: "FAM",
    probeQuencher: "NFQ",
    probeTranscriptMode: "generic",
    standardPcrProtocol: "neb-q5-hot-start-m0493",
    qpcrProtocol: "bio-rad-itaq-sybr",
    qpcrCyclingProfile: "standard",
    qpcrInstrumentProfile: "bio-rad-cfx96",
    rpaProtocol: "twistamp-basic",
    rpaMultiplexPanel: '[{"target":"A","reporter":"FAM"}]',
    longRangeProtocol: "thermo-long-pcr-k018x",
    longRangeTargetLengthKb: "8",
    flankingTemplateClass: "high-molecular-weight",
    digitalProtocol: "bio-rad-qx200-evagreen",
    digitalPartitionFormat: "droplet",
    digitalPlatformId: "bio-rad-qx200",
    digitalPlatformName: "Bio-Rad QX200",
    digitalFragmentationState: "not-assessed",
    digitalPartitionFormatDetail: "8.5k",
    digitalInstrumentModel: "validated-qx200",
    digitalMultiplexPanel: '[{"target":"A","channel":"FAM"}]',
    digitalRunEvidence: '{"status":"reviewed"}',
    circleLength: "2686",
    enzyme: "EcoRI",
    enzymeCohortSize: "3",
    inverseBranch: "restriction-self-ligation",
    leftEndPhosphate: "unresolved",
    rightEndPhosphate: "unresolved",
    circularizationProvenance: "unresolved",
    linearControlProvenance: "unresolved",
    methylationBranch: "unresolved",
    at: "250",
    variantType: "snv",
    variantAt: "250",
    variantRef: "A",
    variantAlt: "G",
    variantCoordinateSystem: "0-based-reference",
    alleleOne: "A",
    alleleTwo: "G",
    geometry: "kasp",
    kaspProtocol: "lgc-standard",
    kaspAssayMode: "biallelic-genotype",
    kaspPlateFormat: "96",
    kaspInstrumentModel: "unresolved",
    kaspRoxPolicy: "unresolved",
    tetraMinBandSeparationBp: "40",
    tetraReadout: "agarose",
    tetraGelPercent: "10",
    tetraLadder: "100 bp ladder",
    tetraRunContext: "validated gel",
    mismatchEvidenceProfile: "arms-experimental-taq",
    nearbyVariantsVcf: "##fileformat=VCFv4.3",
    unknownFlankMin: "100",
    unknownFlankMax: "5000",
    editKind: "substitute",
    editAt: "300",
    editTo: "T",
    editReplacing: "1",
    flank: "12",
    direction: "forward",
    deadZone: "40",
    readLength: "700",
    sequencingProtocol: "bigdye-v3-1",
    sequencingInstrument: "3730xl",
    sequencingInstrumentName: "custom-capillary",
    sequencingFacilitySop: "facility-SOP-7",
    sequencingProvider: "custom-provider",
    sequencingWalkingOverlap: "100",
    sequencingTraceAb1Base64: "QUJDMQ==",
    sequencingTraceFilename: "trace.ab1",
    raceSopRevision: "SOP-7",
    raceSopSha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    raceDirection: "5prime",
    raceAdapter: "generacer-kit-25-0355-vl",
    racePartnerSequence: "CGACTGGAGCACGAGGACACTGA",
    raceSubstrate: "total-rna",
    racePreparation: "GeneRacer Kit 25-0355 Version L",
    raceRound: "primary",
    overlap: "75",
    slide: "20",
    pools: "2",
    segments: "insert,amplified,ACGTACGTACGT",
    circular: "true",
    method: "gibson",
    assemblyProtocol: "neb-e5510",
    outer_tm_min: "57",
    inner_tm_min: "57",
    probe_tm_min: "66",
    shares: "nothing",
    margin: "30",
    singleTube: "false",
    carryoverPrevention: "dUTP-UNG",
    postAmplificationProtocol: "neb-q5-e0554",
    templateMethylationStatus: "unmethylated",
    colonyHostClass: "bacterial",
    colonyPreparation: "direct-transfer",
    colonyProtocolId: "custom-sop",
    colonyProtocolName: "validated-colony-SOP",
    colonyProtocolProvenance: "lab QA system / SOP rev A / 2026-08-01",
    alignmentMode: "auto",
    consensusPolicy: "strict-all-members",
    formulationMode: "mixed-base-synthesis",
    raceChemistry: "generacer-kit-25-0355-vl",
    sequencingDesignProfile: "generic-cycle-sequencing",
    tilingBackend: "primalscheme3",
    mutagenesisTopology: "q5-back-to-back",
    tilingOperation: "scheme-create",
    tilingAlignmentMode: "auto",
    tilingMinBaseFrequency: "0.01",
    tilingTargets: "target-a,target-b",
    tilingDepthTsv: "target\tdepth\nA\t30",
    tilingDropoutThreshold: "0.1",
    olivarSeed: "10",
    schemeVersion: "v1.0.0",
    existingBed: "ref\t0\t100\tprimer_LEFT\t1\t+",
    schemeConfig: "{}",
    regionBed: "ref\t0\t100",
    panelMode: "region-only",
    primerName: "primer_1",
    forwardEnzyme: "EcoRI",
    reverseEnzyme: "BamHI",
    protectiveBases: "6",
    forwardProtectiveSequence: "GACTTA",
    reverseProtectiveSequence: "CAGTTA",
    restrictionDigestProtocol: "neb-cutsmart-standard",
    restrictionDephosphorylationProtocol: "none",
    restrictionLigationProtocol: "neb-t4-dna-ligase-m0202",
    cloningVector: ">vector\nACGTACGTACGT",
    cloningVectorName: "pPCR",
    cloningVectorTopology: "circular",
    cloningCdsStart: "10",
    cloningCdsEnd: "100",
    cloningFusionTag: "none",
    cloningLinkerAa: "GGG",
    cloningVectorJunctionFrame: "0",
    vectorPrimerName: "M13/pUC Forward, 23-mer",
    vectorPrimerSequence: "CCCAGTCACGACGTTGTAAAACG",
    vectorPrimerReadsInto: "start",
    fromRna: "true",
    exonJunctions: "450, 812",
    tailForward: "TGTAAAACGACGGCCAGT",
    tailReverse: "CAGGAAACAGCTATGACC",
    tailProtocol: "neb-general-6bp",
    // The LAMP windows travel by prefix, like the rounds and the constraints.
    w_outer_tm_min: "58",
    w_f2_b2_span_min: "140",
    w_f2_b2_span_max: "220",
    panelMetadata: '{"strain-a":{"role":"inclusivity"}}',
    nontarget: ">near\nACGT",
    alternativeAlignment: ">alt\nACGT",
    alignmentAuditBackend: "mafft",
    formulationTotalConcentrationNm: "500",
    codonUsage: '{"Ala":1}',
    lampDesignStage: "core-first",
    lampMultiplexPlan: '[{"target":"A","reporter":"FAM","quencher":"none"}]',
    cleanupProtocol: "spin-column",
    customTransferSop: "SOP-7",
    transferDilutionFactor: "10",
    transferMode: "dilute-and-transfer",
    transferVolumeUl: "2",
    round1Polymerase: "q5",
    round2Polymerase: "taq",
    round1Conditions: '{"mg_mM":2}',
    round2Conditions: '{"mg_mM":2}',
    round1ThermalProgram: '[{"temperature_c":98,"seconds":30}]',
    round2ThermalProgram: '[{"temperature_c":95,"seconds":30}]',
    inverseReferenceSequence: ">reference\nACGTACGT",
    inverseCandidateEnzymes: "EcoRI,HindIII",
    mappingUseCase: "generic-flank",
    probeInstrumentProfile: "validated-reader",
    probeInternalQuencher: "ZEN",
    probeMgbAuthorityMode: "external-authority-required",
    probeMgbAuthorityPayload: '{"candidate_set_hash":"abc"}',
    probeOpticalAuthorityPayload: '{"instrument":"reader"}',
    probeTranscriptJunctions: "2,4",
    probeVariantPositions: "3,5",
    probeMultiplexPanel: '[{"target":"A","reporter":"FAM","quencher":"Iowa Black FQ"}]',
  };
  const moduleFixed: Record<string, Record<string, string>> = {
    "arms-pcr": { geometry: "arms-two-tube" },
    "tetra-primer-arms": { geometry: "tetra" },
    kasp: { geometry: "kasp", kaspAssayMode: "biallelic-genotype" },
    "gibson-assembly": { method: "gibson", assemblyProtocol: "neb-e5510" },
    "site-directed-mutagenesis": { postAmplificationProtocol: "neb-q5-e0554" },
    "nested-pcr": { singleTube: "false" },
  };
  for (const [key, value] of Object.entries({
    ...filled,
    ...(moduleFixed[moduleId] ?? {}),
    ...overrides,
  })) {
    form.set(key, value);
  }
  return form;
}

/** What one engine's branch actually puts on the wire. */
function scenarioForms(moduleId: string): FormData[] {
  const forms = [everything(moduleId)];

  if (moduleId === "race") {
    forms.push(
      everything(moduleId, {
        raceAdapter: "custom",
        racePartnerSequence: "ACGTACGTACGT",
        raceChemistry: "custom",
        raceSopRevision: "custom-SOP-1",
        raceSopSha256: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      }),
    );
  }
  if (moduleId === "sequencing-primer") {
    forms.push(
      everything(moduleId, {
        sequencingInstrument: "other",
        sequencingInstrumentName: "qualified-custom-capillary",
      }),
    );
  }
  if (moduleId === "digital-pcr") {
    forms.push(
      everything(moduleId, {
        digitalPlatformId: "other-validated",
        digitalPlatformName: "qualified-other-platform",
        digitalProtocol: "not-selected",
      }),
    );
  }
  if (moduleId === "lamp") {
    forms.push(
      everything(moduleId, {
        assayMode: "evaluate",
        existingLampF3: "ACGTACGTACGTACGTAC",
        existingLampB3: "TGCATGCATGCATGCATG",
        existingLampFip: "ACGTACGTACGTACGTACGTACGTACGTACGTACGTAC",
        existingLampBip: "TGCATGCATGCATGCATGCATGCATGCATGCATGCATG",
        existingLampLf: "ACGTACGTACGTACGTAC",
        existingLampLb: "TGCATGCATGCATGCATG",
        existingLampFipF1cLength: "20",
        existingLampBipB1cLength: "20",
      }),
      everything(moduleId, {
        lampDesignIntent: "panel-conservation-aware",
        inclusivity: ">strain-a\nACGTACGTACGTACGTACGT",
      }),
      everything(moduleId, {
        lampDesignIntent: "fixed-primer-anchor",
        lampFixedF3: "ACGT",
      }),
      everything(moduleId, {
        lampDesignIntent: "mutation-anchored-specific",
        lampVariantPosition: "3",
        lampVariantRef: "A",
        lampVariantAlt: "G",
        lampVariantAnchor: "F3",
      }),
    );
  }
  if (moduleId === "tiled-scheme") {
    for (const operation of ["panel-create", "repair-mode", "scheme-replace"] as const) {
      forms.push(everything(moduleId, { tilingOperation: operation }));
    }
  }
  if (moduleId === "site-directed-mutagenesis") {
    forms.push(everything(moduleId, { editKind: "insert", editTo: "ATG", editReplacing: "" }));
    forms.push(everything(moduleId, { editKind: "delete", editTo: "", editReplacing: "3" }));
    forms.push(
      everything(moduleId, {
        editInputMode: "multi",
        editsJson: '[{"kind":"substitute","at":4,"to":"G","replacing":1}]',
      }),
    );
    forms.push(
      everything(moduleId, {
        editInputMode: "amino-acid",
        aaCdsStart: "1",
        aaResidue: "4",
        aaFrom: "A",
        aaTo: "V",
        aaCodon: "GTT",
        codonPolicy: "user-selected-codon",
      }),
    );
    forms.push(
      everything(moduleId, {
        editInputMode: "library",
        libraryMode: "custom",
        libraryAt: "4",
        libraryCodon: "NNK",
      }),
    );
  }

  return forms;
}

function sends(engine: string): Set<string> {
  const sent = new Set<string>();
  for (const moduleId of modulesByEngine().get(engine) ?? []) {
    for (const form of scenarioForms(moduleId)) {
      const built = requestFor(engine, ">t\nACGTACGTACGTACGTACGT", form);
      for (const [key, value] of Object.entries(built)) {
        if (value !== undefined) sent.add(key);
      }
    }
  }
  return sent;
}

/** Every draft key the pages actually draw a control for. */
function rendered(): Set<string> {
  const files = [
    "components/project/workspace.tsx",
    "components/design/engine-fields.tsx",
    ...readdirSync(resolve(WEB, "components/design/engine-fields"))
      .filter((file) => file.endsWith(".tsx"))
      .map((file) => `components/design/engine-fields/${file}`),
    "components/design/engine-closure-fields.tsx",
    "components/design/probe-fields.tsx",
    "components/design/region-picker.tsx",
    "components/design/cloning-tails.tsx",
    "components/design/bench-tools.tsx",
  ];
  const patterns = [
    /set\("(\w+)"/g,
    /text\(draft, "(\w+)"\)/g,
    /draft\.(\w+)/g,
    /onChange\("(\w+)"/g,
    /value\("(\w+)"\)/g,
    /id="(\w+)"/g,
    /name="(\w+)"/g,
    // A control whose key is built from a prop: `<Round prefix="outer" />`
    // draws `outer_product_min` and `outer_product_max` from a template
    // literal, which no literal-key pattern above can see.
    /prefix="(\w+)"/g,
    /\["(existingLamp\w+)",/g,
  ];

  const found = new Set<string>();
  for (const file of files) {
    const source = read(resolve(WEB, file));
    for (const pattern of patterns) {
      for (const [, key] of source.matchAll(pattern)) found.add(key!);
    }
  }
  return found;
}

describe("every engine field is reachable from a page", () => {
  it("found the engines and the controls", () => {
    // The failure mode of a test like this is two empty sets that agree.
    expect(engines().length).toBeGreaterThanOrEqual(11);
    expect(rendered().size).toBeGreaterThan(20);
    expect(modulesByEngine().get("flanking-pair")?.length ?? 0).toBeGreaterThanOrEqual(8);
    expect(sends("flanking-pair").size).toBeGreaterThan(12);
  });

  it.each(engines())("%s", (engine) => {
    const sent = sends(engine);
    const unreachable = accepts(engine)
      .filter((field) => !(field in NOT_SENT))
      .filter((field) => !sent.has(field))
      .sort();

    expect(unreachable, "the engine takes these and no form sends them").toEqual([]);
  });

  it("maps semantic form context into each module's explicit wire contract", () => {
    type Rule = { when: Record<string, string>; required_context: string[] };
    type ModuleContract = {
      engine: string;
      required_context?: string[];
      conditional_required_context?: Rule[];
      wire_required_context?: string[];
      wire_conditional_required_context?: Rule[];
      wire_required_any_of?: string[][];
    };
    const canonical = JSON.parse(read(MODULE_CONTRACTS)) as {
      modules: Record<string, ModuleContract>;
    };
    expect(Object.keys(canonical.modules)).toHaveLength(21);

    const camel = (name: string) =>
      name.replace(/_(\w)/g, (_, letter: string) => letter.toUpperCase());
    const atPath = (root: Record<string, unknown>, sourcePath: string): unknown =>
      sourcePath
        .split(".")
        .map(camel)
        .reduce<unknown>(
          (value, segment) =>
            value && typeof value === "object"
              ? (value as Record<string, unknown>)[segment]
              : undefined,
          root,
        );
    const supplied = (value: unknown) =>
      value !== undefined &&
      value !== null &&
      !(typeof value === "string" && value.trim() === "") &&
      !(Array.isArray(value) && value.length === 0);
    const ruleMatches = (built: Record<string, unknown>, when: Record<string, string>) =>
      Object.entries(when).every(([path, expected]) => atPath(built, path) === expected);
    const assertWire = (
      moduleId: string,
      contract: ModuleContract,
      built: Record<string, unknown>,
    ) => {
      for (const path of contract.wire_required_context ?? []) {
        expect(supplied(atPath(built, path)), `${moduleId} omitted wire context ${path}`).toBe(
          true,
        );
      }
      for (const rule of contract.wire_conditional_required_context ?? []) {
        if (!ruleMatches(built, rule.when)) continue;
        for (const path of rule.required_context) {
          expect(
            supplied(atPath(built, path)),
            `${moduleId} omitted conditional wire context ${path}`,
          ).toBe(true);
        }
      }
      for (const group of contract.wire_required_any_of ?? []) {
        expect(
          group.some((path) => supplied(atPath(built, path))),
          `${moduleId} omitted every wire alternative in ${group.join(" | ")}`,
        ).toBe(true);
      }
    };

    for (const [moduleId, contract] of Object.entries(canonical.modules)) {
      const baseOverrides: Record<string, string> =
        moduleId === "site-directed-mutagenesis"
          ? { editInputMode: "dna", mutagenesisTopology: "q5-back-to-back" }
          : {};
      const built = requestFor(
        contract.engine,
        ">t\nACGTACGTACGTACGTACGT",
        everything(moduleId, baseOverrides),
      ) as Record<string, unknown>;
      assertWire(moduleId, contract, built);

      // Exercise every browser semantic branch, then validate the actual request
      // against the independently-declared wire contract. No snake/camel
      // inference is allowed between these two layers.
      for (const semantic of contract.conditional_required_context ?? []) {
        const overrides = Object.fromEntries(
          Object.entries(semantic.when).map(([path, value]) => [draftFieldForContext(path), value]),
        );
        if (moduleId === "site-directed-mutagenesis") {
          Object.assign(overrides, { mutagenesisTopology: "q5-back-to-back" });
        }
        const branch = requestFor(
          contract.engine,
          ">t\nACGTACGTACGTACGTACGT",
          everything(moduleId, overrides),
        ) as Record<string, unknown>;
        assertWire(moduleId, contract, branch);
      }
    }
  });

  it("and every key the builder reads is one some page draws", () => {
    // The other direction: a value the builder would send that no control
    // collects, which is a field nobody can use rather than one nobody sees.
    const source = read(resolve(WEB, "lib/projects/request.ts"));
    const readByBuilder = [...source.matchAll(/form, "(\w+)"/g)].map(([, key]) => key!);

    const drawn = rendered();
    // A prefix family is collected wholesale — `roundFrom(form, "outer")` takes
    // every `outer_*` on the form — so its members are the controls and the
    // bare name never appears as one.
    const families = ["c_", "outer_", "inner_", "probe_"];

    const orphans = [...new Set(readByBuilder)]
      .filter((key) => !drawn.has(key))
      .filter((key) => !families.some((prefix) => key.startsWith(prefix)))
      .filter((key) => ![...drawn].some((one) => one.startsWith(`${key}_`)))
      // Supplied by the page plan rather than chosen: three genotyping assays
      // share one engine and are told apart by `geometry`, and when it was a
      // dropdown the tetra-primer page designed an ARMS assay and reported it
      // as a success.
      .filter((key) => key !== "geometry")
      .filter((key) => !["lamp", "probe"].includes(key))
      .sort();

    expect(orphans, "the builder would send these and no control fills them").toEqual([]);
  });
});

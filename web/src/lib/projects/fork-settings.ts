/**
 * Turn the request saved with a run back into the flat strings used by the
 * workspace draft. Shared runs are deliberately immutable, but a fork must
 * remain a reproducible starting point rather than just a copy of its title.
 */

import { LAMP_BENCH_FIELD_MAP } from "@/lib/lamp-contract";
import { restoreFlankingNumericContext, restoreWindows } from "./draft-codec";

type Value = unknown;
type Settings = Record<string, string>;

function put(out: Settings, key: string, value: Value): void {
  if (value === undefined || value === null || value === "") return;
  out[key] = String(value);
}

function putJson(out: Settings, key: string, value: Value): void {
  if (value === undefined || value === null || value === "") return;
  if (typeof value === "object") {
    out[key] = JSON.stringify(value, null, 2);
    return;
  }
  out[key] = String(value);
}

function oneBased(value: Value): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value + 1 : undefined;
}

function putRound(out: Settings, prefix: string, value: Value): void {
  if (!value || typeof value !== "object" || Array.isArray(value)) return;
  for (const [key, entry] of Object.entries(value)) put(out, `${prefix}_${key}`, entry);
}

function putNumbers(out: Settings, prefix: string, value: Value): void {
  if (!value || typeof value !== "object" || Array.isArray(value)) return;
  for (const [key, entry] of Object.entries(value)) put(out, `${prefix}${key}`, entry);
}

/** The inverse of the request builder's zero-based coordinate conversion. */
export function forkSettingsFromRequest(
  request: Record<string, Value>,
  targetName?: string,
): Settings {
  const out: Settings = {};
  put(out, "name", targetName);

  for (const key of [
    "template",
    "polymerase",
    "purpose",
    "background",
    "inclusivity",
    "inclusivityPanelProvenance",
    "backgroundPanelProvenance",
    "speciesPanelSelectionRationale",
    "speciesTargetTaxid",
    "speciesTaxonomySnapshot",
    "speciesDatabaseSnapshot",
    "speciesPanelAccessionManifest",
    "speciesPanelAccessionAuthorityManifest",
    "speciesPanelRecordMetadataManifest",
    "speciesPanelRetrievedDate",
    "howMany",
    "maxMismatches",
    "tetraMinBandSeparationBp",
    "nearbyVariantsVcf",
    "mismatchEvidenceProfile",
    "tetraReadout",
    "tetraGelPercent",
    "tetraLadder",
    "tetraRunContext",
    "direction",
    "deadZone",
    "readLength",
    "sequencingProtocol",
    "sequencingDesignProfile",
    "sequencingProvider",
    "sequencingUniversalPrimerScan",
    "sequencingPrimerWalking",
    "sequencingBidirectional",
    "sequencingInstrument",
    "sequencingInstrumentName",
    "sequencingFacilitySop",
    "sequencingWalkingOverlap",
    "raceDirection",
    "raceChemistry",
    "raceAdapter",
    "racePartnerSequence",
    "raceSopRevision",
    "raceSopSha256",
    "raceSubstrate",
    "racePreparation",
    "raceRound",
    "flank",
    "overlap",
    "pools",
    "method",
    "assemblyProtocol",
    "geometry",
    "parameterSet",
    "probeProtocol",
    "probeChemistry",
    "probeReporter",
    "probeQuencher",
    "probeInternalQuencher",
    "probeInstrumentProfile",
    "probeMgbAuthorityMode",
    "probeTranscriptMode",
    "standardPcrProtocol",
    "qpcrProtocol",
    "rpaProtocol",
    "longRangeProtocol",
    "digitalProtocol",
    "digitalPartitionFormat",
    "digitalPlatformId",
    "digitalPlatformName",
    "digitalInstrumentModel",
    "digitalFragmentationState",
    "digitalMultiplexMode",
    "colonyHostClass",
    "colonyPreparation",
    "colonyProtocolId",
    "colonyProtocolName",
    "colonyProtocolProvenance",
    "lampGeometryProfile",
    "lampInnerLinker",
    "lampProtocol",
    "lampReadout",
    "lampReadoutChemistry",
    "lampSampleMatrix",
    "lampSamplePreparation",
    "lampFormulation",
    "lampConfirmationMode",
    "lampDetectionTopology",
    "lampDesignIntent",
    "lampDesignStage",
    "lampVariantAnchor",
    "lampVariantAlt",
    "lampVariantRef",
    "lampVariantPosition",
    "lampFixedLB",
    "lampFixedLF",
    "lampFixedBIP",
    "lampFixedFIP",
    "lampFixedB3",
    "lampFixedF3",
    "lampLoopPolicy",
    "lampCarryoverStrategy",
    "lampReconstitutionX",
    "lampSpecificityAdditive",
    "lampAccelerationAdditive",
    "lampPrimerKineticsProfile",
    "lampPreincubationStrategy",
    "lampSampleBufferType",
    "lampInstrumentProfile",
    "kaspProtocol",
    "kaspAssayMode",
    "kaspPlateFormat",
    "kaspInstrumentModel",
    "kaspRoxPolicy",
    "enzyme",
    "enzymeCohortSize",
    "mappingUseCase",
    "circleLength",
    "inverseBranch",
    "leftEndPhosphate",
    "rightEndPhosphate",
    "circularizationProvenance",
    "linearControlProvenance",
    "methylationBranch",
    "unknownFlankMin",
    "unknownFlankMax",
    "margin",
    "carryoverPrevention",
    "transferMode",
    "cleanupProtocol",
    "transferVolumeUl",
    "transferDilutionFactor",
    "customTransferSop",
    "round1Polymerase",
    "round2Polymerase",
    "round1Conditions",
    "round2Conditions",
    "round1ThermalProgram",
    "round2ThermalProgram",
    "mutagenesisTopology",
    "codonPolicy",
    "codonUsage",
    "libraryMode",
    "templateMethylationStatus",
    "postAmplificationProtocol",
    "alignmentMode",
    "consensusPolicy",
    "panelMetadata",
    "formulationMode",
    "formulationTotalConcentrationNm",
    "nontarget",
    "alternativeAlignment",
    "alignmentAuditBackend",
    "tilingOperation",
    "tilingDepthTsv",
    "tilingBackend",
    "tilingAlignmentMode",
    "tilingMinBaseFrequency",
    "tilingDropoutThreshold",
    "tilingBacktrack",
    "tilingHighGc",
    "olivarSeed",
    "olivarDegenerateMode",
    "olivarCheckVariants",
    "schemeVersion",
    "existingBed",
    "schemeConfig",
    "regionBed",
    "panelMode",
    "primerName",
    "cloningVector",
    "cloningVectorName",
    "cloningVectorTopology",
    "restrictionDigestProtocol",
    "restrictionDephosphorylationProtocol",
    "restrictionLigationProtocol",
    "cloningCodingIntent",
    "cloningCdsStart",
    "cloningCdsEnd",
    "cloningStopCodonPolicy",
    "cloningFusionTag",
    "cloningLinkerAa",
    "cloningVectorJunctionFrame",
  ])
    put(out, key, request[key]);

  // Normalize the historical nested carry-over identity to the canonical
  // current strategy ID used by the authority and UI. The Python/Rust boundary
  // still accepts the old alias when an archived request is executed directly.
  if (request.carryoverPrevention === "dUTP-UNG")
    put(out, "carryoverPrevention", "dutp-ung-strategy-only");

  for (const key of [
    "lampSampleInputPercent",
    "lampSampleBufferPh",
    "lampSampleBufferPercent",
    "lampTransportMediumPercent",
    "lampBileSaltMgMl",
    "lampCaryBlairPercent",
    "lampUpstreamGuanidineMm",
  ] as const)
    put(out, key, request[key]);

  for (const key of [
    "fromRna",
    "circular",
    "singleTube",
    "lowercaseMasking",
    "racePolyadenylated",
  ]) {
    if (typeof request[key] === "boolean") put(out, key, request[key]);
  }

  for (const [source, destination] of [
    ["targetStart", "targetStart"],
    ["at", "at"],
  ] as const)
    put(out, destination, oneBased(request[source]));
  put(out, "targetLength", request.targetLength);

  if (request.method) put(out, "assemblyMethod", request.method);

  if (request.mode === "validate-existing") put(out, "assayMode", "evaluate");
  else if (request.mode === "design") put(out, "assayMode", "design");

  if (
    request.lampBenchOptimization &&
    typeof request.lampBenchOptimization === "object" &&
    !Array.isArray(request.lampBenchOptimization)
  ) {
    const optimization = request.lampBenchOptimization as Record<string, Value>;
    for (const [destination, source] of LAMP_BENCH_FIELD_MAP) {
      put(out, destination, optimization[source]);
    }
  }

  if (
    request.workflowEvidence &&
    typeof request.workflowEvidence === "object" &&
    !Array.isArray(request.workflowEvidence)
  ) {
    for (const [key, value] of Object.entries(request.workflowEvidence as Record<string, Value>)) {
      put(out, key, value);
    }
  }

  if (
    request.existingSet &&
    typeof request.existingSet === "object" &&
    !Array.isArray(request.existingSet)
  ) {
    const existing = request.existingSet as Record<string, Value>;
    for (const [from, to] of [
      ["f3", "existingLampF3"],
      ["b3", "existingLampB3"],
      ["fip", "existingLampFip"],
      ["bip", "existingLampBip"],
      ["lf", "existingLampLf"],
      ["lb", "existingLampLb"],
      ["fipF1cLength", "existingLampFipF1cLength"],
      ["bipB1cLength", "existingLampBipB1cLength"],
    ] as const)
      put(out, to, existing[from]);
  }

  if (Array.isArray(request.excluded)) {
    const regions = request.excluded
      .filter((entry): entry is [number, number] => Array.isArray(entry) && entry.length === 2)
      .map(([start, length]) => `${start + 1}-${start + length}`);
    put(out, "avoided", regions.join(","));
  }
  if (Array.isArray(request.variants)) {
    put(out, "variants", request.variants.map((entry) => entry + 1).join(","));
  }
  if (Array.isArray(request.exonJunctions)) {
    put(out, "exonJunctions", request.exonJunctions.join(","));
  }

  putNumbers(out, "c_", request.constraints);
  putRound(out, "outer", request.outer);
  putRound(out, "inner", request.inner);
  putRound(out, "probe", request.probe);
  put(out, "shares", request.shares);

  if (request.edit && typeof request.edit === "object" && !Array.isArray(request.edit)) {
    const edit = request.edit as Record<string, Value>;
    put(out, "editKind", edit.kind);
    put(out, "editAt", oneBased(edit.at));
    put(out, "editTo", edit.to);
    put(out, "editReplacing", edit.replacing);
  }

  if (request.variant && typeof request.variant === "object" && !Array.isArray(request.variant)) {
    const variant = request.variant as Record<string, Value>;
    put(out, "variantType", variant.type ?? variant.kind);
    put(out, "variantAt", oneBased(variant.at));
    put(out, "variantRef", variant.ref);
    put(out, "variantAlt", variant.alt);
    put(
      out,
      "variantReferenceAccession",
      variant.referenceAccession ?? variant.reference_accession,
    );
    put(out, "variantAssembly", variant.assembly);
    put(out, "variantCoordinateSystem", variant.coordinateSystem ?? variant.coordinate_system);
    put(out, "variantStrand", variant.strand);
    put(out, "variantRsid", variant.rsid);
  } else if (typeof request.at === "number" || Array.isArray(request.alleles)) {
    // Legacy discriminating projects used `at` + two `alleles` instead
    // of the typed variant object. Preserve those projects without silently
    // changing their coordinate or allele semantics when they are forked.
    put(out, "variantType", "snv");
    put(out, "variantAt", oneBased(request.at));
    if (Array.isArray(request.alleles)) {
      put(out, "variantRef", request.alleles[0]);
      put(out, "variantAlt", request.alleles[1]);
    }
  }

  if (Array.isArray(request.edits)) {
    put(out, "editInputMode", "multi");
    const visible = request.edits.map((entry) => {
      if (!entry || typeof entry !== "object" || Array.isArray(entry)) return entry;
      const row = { ...(entry as Record<string, Value>) };
      if (typeof row.at === "number") row.at = row.at + 1;
      return row;
    });
    put(out, "editsJson", JSON.stringify(visible, null, 2));
  }
  if (
    request.aminoAcidEdit &&
    typeof request.aminoAcidEdit === "object" &&
    !Array.isArray(request.aminoAcidEdit)
  ) {
    const aa = request.aminoAcidEdit as Record<string, Value>;
    put(out, "editInputMode", "amino-acid");
    put(out, "aaCdsStart", oneBased(aa.cdsStart));
    put(out, "aaResidue", aa.residue);
    put(out, "aaFrom", aa.fromAa);
    put(out, "aaTo", aa.toAa);
    put(out, "aaCodon", aa.codon);
  }
  if (
    request.libraryEdit &&
    typeof request.libraryEdit === "object" &&
    !Array.isArray(request.libraryEdit)
  ) {
    const lib = request.libraryEdit as Record<string, Value>;
    put(out, "editInputMode", "library");
    put(out, "libraryAt", oneBased(lib.at));
    put(out, "libraryCodon", lib.codon);
  }

  if (Array.isArray(request.alleles)) {
    put(out, "alleleOne", request.alleles[0]);
    put(out, "alleleTwo", request.alleles[1]);
  }

  if (Array.isArray(request.segments)) {
    const rows = request.segments.filter((entry): entry is Record<string, Value> =>
      Boolean(entry && typeof entry === "object"),
    );
    const rich = rows.some((entry) =>
      [
        "restriction",
        "features",
        "provenance",
        "concentrationNgUl",
        "massNg",
        "volumeUl",
        "orientation",
      ].some((key) => entry[key] !== undefined && entry[key] !== null && entry[key] !== ""),
    );
    if (rich) {
      put(out, "segments", JSON.stringify(rows, null, 2));
    } else {
      const lines = rows
        .map((entry) => [entry.name ?? "", entry.kind ?? "", entry.sequence ?? ""].join(","))
        .filter((line) => line.split(",")[2]);
      put(out, "segments", lines.join("\n"));
    }
  }

  for (const [requestKey, formKey] of [
    ["codonUsage", "codonUsage"],
    ["round1Conditions", "round1Conditions"],
    ["round2Conditions", "round2Conditions"],
    ["round1ThermalProgram", "round1ThermalProgram"],
    ["round2ThermalProgram", "round2ThermalProgram"],
  ] as const) {
    const value = request[requestKey];
    if (value && typeof value === "object") put(out, formKey, JSON.stringify(value, null, 2));
  }

  if (request.tails && typeof request.tails === "object" && !Array.isArray(request.tails)) {
    const tails = request.tails as Record<string, Value>;
    for (const key of [
      "tailProtocol",
      "forwardEnzyme",
      "reverseEnzyme",
      "protectiveBases",
      "forwardProtectiveSequence",
      "reverseProtectiveSequence",
      "forward",
      "reverse",
    ])
      put(
        out,
        key === "forward" ? "tailForward" : key === "reverse" ? "tailReverse" : key,
        tails[key],
      );
  }

  if (request.vectorPrimer && typeof request.vectorPrimer === "object") {
    const primer = request.vectorPrimer as Record<string, Value>;
    for (const [from, to] of [
      ["name", "vectorPrimerName"],
      ["sequence", "vectorPrimerSequence"],
      ["readsInto", "vectorPrimerReadsInto"],
      ["vector", "vectorSequence"],
    ] as const)
      put(out, to, primer[from]);
  }

  restoreFlankingNumericContext(out, request.flankingNumericContext);
  restoreWindows(out, request.windows);

  putJson(out, "probeOpticalAuthorityPayload", request.probeOpticalAuthorityPayload);
  putJson(out, "probeMgbAuthorityPayload", request.probeMgbAuthorityPayload);
  putJson(out, "probeMultiplexPanel", request.probeMultiplexPanel);
  putJson(out, "lampMultiplexPlan", request.lampMultiplexPlan);
  putJson(out, "rpaMultiplexPanel", request.rpaMultiplexPanel);
  putJson(out, "digitalMultiplexPanel", request.digitalMultiplexPanel);
  putJson(out, "digitalRunEvidence", request.digitalRunEvidence);
  putJson(out, "tilingTargets", request.tilingTargets);
  return out;
}

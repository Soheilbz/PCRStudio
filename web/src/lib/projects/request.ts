/**
 * One design request, built from what a form carried.
 *
 * Split out of `actions.ts` because it is pure: a `FormData` goes in and an
 * object goes out, with nothing awaited and no session touched. It lived there
 * only because that is where it was written — and a `"use server"` module
 * cannot export a synchronous function, so the only way to test it was to read
 * it out of its own source with a regular expression. That test existed
 * briefly, and its parser was wrong twice before this move made it unnecessary.
 *
 * Every engine sets `deny_unknown_fields`, deliberately: a misspelt parameter
 * that is silently ignored produces a run whose settings are not the settings
 * somebody asked for. The cost is that one field too many does not degrade —
 * it fails. So which fields each branch sends is the contract this file keeps.
 */

import { parseVariants } from "@/lib/variants";
import type { DesignPayload } from "@/lib/contracts/design-requests";
import { LAMP_BENCH_FIELD_MAP } from "@/lib/lamp-contract";
import {
  outwardClosureFields,
  probeClosureFields,
  singleClosureFields,
  tilingClosureFields,
} from "./engine-request-extensions";
import { flankingNumericContextFromDraft, windowsFromDraft } from "./draft-codec";
/** One field, as a trimmed string. */
function field(form: FormData, name: string): string {
  const value = form.get(name);
  return typeof value === "string" ? value.trim() : "";
}

/** One field as a number, or nothing when it was left empty. */
function optionalNumber(form: FormData, name: string): number | undefined {
  const raw = field(form, name);
  if (!raw) return undefined;
  const value = Number(raw);
  if (!Number.isFinite(value)) {
    throw new Error(`${name} must be a finite number.`);
  }
  return value;
}

/** Normalize an old saved-draft alias before it crosses the current wire contract. */
function currentProbeProtocol(form: FormData): DesignPayload["probeProtocol"] | undefined {
  const selected = field(form, "probeProtocol");
  if (!selected) return undefined;
  if (selected === "taqman-mgb") return "taqman-mgb-reference";
  return selected as DesignPayload["probeProtocol"];
}
/** Parse a dynamic numeric form entry without turning malformed input into absence. */
function numberText(raw: string, name: string): number {
  const value = Number(raw);
  if (!Number.isFinite(value)) {
    throw new Error(`${name} must be a finite number.`);
  }
  return value;
}

/**
 * Whatever constraints the form sent.
 *
 * Fields are prefixed rather than listed, because the list belongs to the
 * engine and is published by it. Hard-coding one here is how a setting gets
 * accepted by the form and refused by the run — or worse, dropped in between.
 */
const CONSTRAINT_PREFIX = "c_";

const WORKFLOW_EVIDENCE_FIELDS: Record<
  string,
  { numeric: readonly string[]; textual: readonly string[] }
> = {
  "colony-pcr": {
    numeric: [
      "colonyExpectedPositiveBandBp",
      "colonyExpectedEmptyBandBp",
      "colonyMinimumResolvableDifferenceBp",
    ],
    textual: ["colonyScreenStrategy"],
  },
  "qpcr-sybr": {
    numeric: [
      "qpcrStandardCurveSlope",
      "qpcrStandardCurveR2",
      "qpcrEfficiencyPercent",
      "qpcrLod",
      "qpcrLloq",
      "qpcrUloq",
      "qpcrReplicates",
      "qpcrCqMean",
      "qpcrDynamicRangeLogs",
    ],
    textual: [
      "qpcrNtcStatus",
      "qpcrNoRtStatus",
      "qpcrMeltEvidence",
      "qpcrValidationNotes",
      "qpcrInstrument",
      "qpcrSoftwareVersion",
      "qpcrBaselineMethod",
      "qpcrThresholdMethod",
      "qpcrPositiveControlStatus",
      "qpcrRawDataReference",
      "qpcrReferenceGenes",
      "qpcrNormalizationMethod",
      "qpcrInhibitionAssessment",
    ],
  },
  "digital-pcr": {
    numeric: [
      "dpcrTotalPartitions",
      "dpcrAcceptedPartitions",
      "dpcrPositivePartitions",
      "dpcrNegativePartitions",
      "dpcrRainPartitions",
      "dpcrPartitionVolumeUl",
      "dpcrDilutionFactor",
      "dpcrCopiesPerUl",
      "dpcrCiLower",
      "dpcrCiUpper",
      "dpcrLob",
      "dpcrLod",
      "dpcrLoq",
      "dpcrMeasurementUncertaintyPercent",
    ],
    textual: [
      "dpcrThresholdMethod",
      "dpcrValidationNotes",
      "dpcrInstrumentSoftwareVersion",
      "dpcrPartitionVolumeAuthority",
      "dpcrPlateLot",
      "dpcrVpf",
      "dpcrControlStatus",
      "dpcrRainPolicy",
      "dpcrRawDataReference",
    ],
  },
  rpa: {
    numeric: ["rpaScreenCandidateCount", "rpaScreenReplicates"],
    textual: ["rpaScreenResponse", "rpaScreenControls", "rpaScreenNotes"],
  },
  lamp: {
    numeric: ["lampValidationSetCount", "lampValidationReplicates"],
    textual: [
      "lampValidationResponse",
      "lampValidationInputs",
      "lampNtcStatus",
      "lampPositiveControlStatus",
      "lampNoRtStatus",
      "lampObservedLod",
      "lampTimeToPositive",
      "lampConfirmationEvidence",
      "lampInclusivityEvidence",
      "lampExclusivityEvidence",
      "lampMatrixSpikeEvidence",
      "lampWithinRunEvidence",
      "lampBetweenRunEvidence",
      "lampRobustnessEvidence",
      "lampSampleMatrixEvidence",
      "lampValidationNotes",
    ],
  },
  "universal-primers": {
    numeric: ["universalScreenSetCount", "universalReplicates"],
    textual: [
      "universalNtcStatus",
      "universalPositiveControlStatus",
      "universalObservedCoverage",
      "universalInclusivityEvidence",
      "universalExclusivityEvidence",
      "universalFormulationEvidence",
      "universalRawDataReference",
      "universalValidationNotes",
    ],
  },
  "arms-pcr": {
    numeric: ["armsReplicates", "armsConcordantCalls"],
    textual: [
      "armsNtcStatus",
      "armsPositiveControlA",
      "armsPositiveControlB",
      "armsHeterozygousControl",
      "armsObservedReadout",
      "armsRawDataReference",
      "armsValidationNotes",
    ],
  },
  "tetra-primer-arms": {
    numeric: ["tetraReplicates", "tetraConcordantCalls"],
    textual: [
      "tetraNtcStatus",
      "tetraKnownGenotypeControls",
      "tetraObservedBands",
      "tetraOuterControlBand",
      "tetraGelImageReference",
      "tetraValidationNotes",
    ],
  },
  kasp: {
    numeric: [
      "kaspSamples",
      "kaspCalledSamples",
      "kaspCallRatePercent",
      "kaspControlConcordancePercent",
    ],
    textual: [
      "kaspNtcStatus",
      "kaspKnownGenotypeControls",
      "kaspRareAlleleControl",
      "kaspInstrumentSoftware",
      "kaspEndpointDataReference",
      "kaspClusterReview",
      "kaspAmbiguousWells",
      "kaspValidationNotes",
    ],
  },
  "gibson-assembly": {
    numeric: [
      "assemblyInputFragmentCount",
      "assemblyColonyCount",
      "assemblyNegativeControlColonies",
      "assemblyVerifiedCloneCount",
    ],
    textual: [
      "assemblyFragmentQc",
      "assemblyConcentrationReference",
      "assemblyMixLot",
      "assemblyIncubationEvidence",
      "assemblyTransformationMethod",
      "assemblyColonyPcrEvidence",
      "assemblyRestrictionVerification",
      "assemblySequenceVerification",
      "assemblyValidationNotes",
    ],
  },
  "site-directed-mutagenesis": {
    numeric: [
      "mutagenesisColonyCount",
      "mutagenesisClonesScreened",
      "mutagenesisVerifiedCloneCount",
    ],
    textual: [
      "mutagenesisPcrEvidence",
      "mutagenesisDpnIKldEvidence",
      "mutagenesisTransformationEvidence",
      "mutagenesisSequenceReference",
      "mutagenesisUnintendedMutationStatus",
      "mutagenesisValidationNotes",
    ],
  },
  "nested-pcr": {
    numeric: ["nestedRound1ObservedBandBp", "nestedRound2ObservedBandBp", "nestedObservedLod"],
    textual: [
      "nestedRound1Ntc",
      "nestedRound2Ntc",
      "nestedPositiveControl",
      "nestedPrePcrArea",
      "nestedRound1Area",
      "nestedTransferArea",
      "nestedRound2Area",
      "nestedTransferRunId",
      "nestedSourceTubeWell",
      "nestedDestinationTubeWell",
      "nestedRawDataReference",
      "nestedSequenceConfirmation",
      "nestedValidationNotes",
    ],
  },
  "qpcr-probe": {
    numeric: [
      "probeEfficiencyPercent",
      "probeStandardCurveR2",
      "probeLod",
      "probeLloq",
      "probeUloq",
      "probeReplicates",
      "probeCqMean",
      "probeDynamicRangeLogs",
    ],
    textual: [
      "probeNtcStatus",
      "probeNoRtStatus",
      "probePositiveControlStatus",
      "probeInstrumentEvidence",
      "probeSoftwareVersion",
      "probeBaselineMethod",
      "probeThresholdMethod",
      "probeRawDataReference",
      "probeReferenceGenes",
      "probeNormalizationMethod",
      "probeInhibitionAssessment",
      "probeValidationNotes",
    ],
  },
  "inverse-pcr": {
    numeric: ["inverseObservedBandBp"],
    textual: [
      "inverseDigestEvidence",
      "inverseLigationEvidence",
      "inverseCircleEvidence",
      "inverseLinearControlEvidence",
      "inverseSequenceConfirmation",
      "inverseMappingReference",
      "inverseValidationNotes",
    ],
  },
  race: {
    numeric: ["raceObservedBandBp", "raceReplicates"],
    textual: [
      "raceRnaQc",
      "raceDnaseEvidence",
      "raceRtEvidence",
      "raceOuterPcrEvidence",
      "raceNestedPcrEvidence",
      "raceCloneReference",
      "raceSequenceConfirmation",
      "raceValidationNotes",
    ],
  },
  "sequencing-primer": {
    numeric: ["sequencingObservedReadLength", "sequencingMeanQuality"],
    textual: [
      "sequencingTraceReference",
      "sequencingMixedPeakStatus",
      "sequencingInstrumentEvidence",
      "sequencingRunId",
      "sequencingValidationNotes",
    ],
  },
  "tiled-scheme": {
    numeric: ["tilingMeanDepth", "tilingMinimumDepth", "tilingDropoutAmplicons"],
    textual: [
      "tilingDepthReference",
      "tilingPoolBalanceEvidence",
      "tilingVariantEscapeEvidence",
      "tilingSequencingRunId",
      "tilingValidationNotes",
    ],
  },
};

/**
 * Bench/run evidence that travels with a saved run without participating in sequence ranking.
 *
 * Keeping this mapping explicit prevents arbitrary hidden form state from becoming scientific
 * provenance. Numeric evidence is parsed as a finite number; textual evidence is preserved as the
 * user's trimmed record. Empty fields mean unresolved/not-recorded and are omitted rather than
 * converted to favourable defaults.
 */
function workflowEvidenceFrom(
  form: FormData,
  moduleId: string,
): Record<string, string | number | boolean | null> | undefined {
  const spec = WORKFLOW_EVIDENCE_FIELDS[moduleId];
  if (!spec) return undefined;

  const evidence: Record<string, string | number | boolean | null> = {};
  for (const key of spec.numeric) {
    const value = optionalNumber(form, key);
    if (value !== undefined) evidence[key] = value;
  }
  for (const key of spec.textual) {
    const value = field(form, key);
    if (value) evidence[key] = value;
  }
  return Object.keys(evidence).length ? evidence : undefined;
}

function constraintsFrom(form: FormData): Record<string, number> | undefined {
  const given: Record<string, number> = {};

  for (const [key, value] of form.entries()) {
    if (!key.startsWith(CONSTRAINT_PREFIX) || typeof value !== "string") continue;
    const text = value.trim();
    // Empty means "use this engine's own default", which is not zero.
    if (!text) continue;
    given[key.slice(CONSTRAINT_PREFIX.length)] = numberText(text, key);
  }

  return Object.keys(given).length ? given : undefined;
}

/**
 * Regions no primer may overlap.
 *
 * The form carries them as `from-to,from-to` because that survives a draft
 * round-trip as a plain string. The engine wants `[start, length]` pairs,
 * zero-based, which is what Primer3 means by an excluded region.
 */
/**
 * A coordinate the person typed, in the coordinate the engines use.
 *
 * The interface counts bases from one, because that is how a sequence is read
 * and written everywhere outside a program. Primer3 counts from zero, and
 * nothing in this build sets `PRIMER_FIRST_BASE_INDEX` to change that.
 *
 * The two frames were being crossed in different places by different amounts:
 * `excludedFrom` converted correctly, and `targetStart` twelve lines below it
 * did not. Measured on a thousand-base template, a region drawn over the last
 * ten bases was refused with "the target at 991..1001 falls outside a template
 * of 1000 bases" — a region that is inside the template, reported as outside
 * it, because it had been shifted one base right on the way down.
 *
 * So there is one function, and every coordinate leaving this file goes
 * through it. `undefined` passes through untouched: a coordinate nobody gave
 * is not a coordinate to shift.
 */
function zeroBased(value: number | undefined): number | undefined {
  // Do not clamp invalid user input to the first base. That turns a typo into
  // a different, apparently valid experiment. The Rust request schema and
  // engine validation reject negative/zero coordinates with a useful error.
  return value === undefined ? undefined : value - 1;
}

/**
 * Positions the template is known to vary at.
 *
 * The box takes anything a person is likely to have — a comma list, a pasted
 * column, VCF lines — and `parseVariants` reduces it to numbers counted from
 * one. Here they cross into the frame the engines use, through the same
 * `zeroBased` every other coordinate on this page goes through: the two frames
 * were being crossed by different amounts in different places once already,
 * and one function is what stopped that.
 *
 * Undefined when nothing was typed, so "no variants given" reaches the worker
 * as an absent field rather than an empty list. The worker words those two
 * differently, and it should: nobody asked is not the same as asked and clean.
 */
function variantsFrom(form: FormData): number[] | undefined {
  const positions = parseVariants(field(form, "variants"));
  if (!positions.length) return undefined;

  // Sorted and de-duplicated here as well as in the worker. Cheap, and it
  // means what travels is what a reader would expect to see. Keep the
  // narrowing explicit rather than asserting away `undefined`: zeroBased is a
  // shared helper whose signature must also support absent optional fields.
  const shifted = positions
    .map((one) => zeroBased(one))
    .filter((one): one is number => one !== undefined);
  return Array.from(new Set<number>(shifted)).sort((a, b) => a - b);
}

/**
 * Transcript boundaries are entered as the number of the last base in the
 * upstream exon: 450 means the boundary between bases 450 and 451. That is
 * already the zero-based boundary coordinate the worker uses, so unlike a
 * base position it is not decremented.
 */
function exonJunctionsFrom(form: FormData): number[] | undefined {
  const raw = field(form, "exonJunctions");
  if (!raw) return undefined;

  const values = raw
    .split(/[\s,;]+/u)
    .filter(Boolean)
    .map(Number);
  if (values.some((value) => !Number.isInteger(value) || value < 1)) {
    throw new Error(
      "Exon-junction boundaries must be positive integers, separated by commas or spaces.",
    );
  }
  return values;
}

function excludedFrom(form: FormData): [number, number][] | undefined {
  const packed = field(form, "avoided");
  if (!packed) return undefined;

  const regions: [number, number][] = [];
  for (const entry of packed.split(",")) {
    const [rawFrom, rawTo] = entry.split("-");
    const fromText = (rawFrom ?? "").trim();
    const toText = (rawTo ?? "").trim();
    if (!fromText || !toText) {
      throw new Error("Avoided regions must use the format start-end.");
    }
    const from = numberText(fromText, "avoided start");
    const to = numberText(toText, "avoided end");
    if (!Number.isInteger(from) || !Number.isInteger(to) || from < 1 || to < from) {
      throw new Error("Avoided-region coordinates must be integers with end ≥ start.");
    }
    regions.push([zeroBased(from)!, to - from + 1]);
  }

  return regions.length ? regions : undefined;
}

/**
 * One design request, carrying only what its engine accepts.
 *
 * Every engine refuses fields it does not recognise, which is deliberate: a
 * misspelt parameter that is silently ignored produces a run whose settings are
 * not the settings somebody asked for. The cost of that strictness is that the
 * client cannot send one superset and let each engine take what it wants — a
 * tiling scheme has no target to amplify across, a mutagenic pair has no
 * product to size, and neither of them would accept a background genome to
 * screen against.
 *
 * So the shape is decided here, by engine, rather than by hoping every field
 * happens to be harmless everywhere.
 */
/**
 * One round's constraints, for the engine that designs two.
 *
 * Prefixed rather than nested because a form is flat, and named for the round
 * rather than numbered: `outer_product_min` says which reaction it belongs to
 * where `constraints_1_product_min` would not.
 */
function roundFrom(form: FormData, round: string): Record<string, number> | undefined {
  const collected: Record<string, number> = {};
  for (const [key, value] of form.entries()) {
    if (!key.startsWith(`${round}_`) || typeof value !== "string" || !value.trim()) continue;
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) {
      throw new Error(`${key} must be a finite number.`);
    }
    collected[key.slice(round.length + 1)] = parsed;
  }
  return Object.keys(collected).length ? collected : undefined;
}

/**
 * The restriction sites to put on the two primer ends.
 *
 * `undefined` when neither end carries one, so a page that never asked sends
 * nothing rather than an empty block — the engine refuses unknown fields and a
 * half-filled one would be a different request from no request at all.
 *
 * Protective-base values on their own are dropped: a number of bases to leave
 * outside sites that do not exist describes nothing.
 */
function tailsFrom(form: FormData): Record<string, string | number> | undefined {
  const forward = field(form, "forwardEnzyme").trim();
  const reverse = field(form, "reverseEnzyme").trim();
  if (!forward && !reverse) return undefined;

  const built: Record<string, string | number> = {};
  const tailProtocol = field(form, "tailProtocol").trim();
  if (tailProtocol) built.tailProtocol = tailProtocol;
  if (forward) built.forwardEnzyme = forward;
  if (reverse) built.reverseEnzyme = reverse;
  const bases = optionalNumber(form, "protectiveBases");
  if (bases !== undefined) built.protectiveBases = bases;
  const forwardProtectiveSequence = field(form, "forwardProtectiveSequence").trim();
  if (forwardProtectiveSequence) built.forwardProtectiveSequence = forwardProtectiveSequence;
  const reverseProtectiveSequence = field(form, "reverseProtectiveSequence").trim();
  if (reverseProtectiveSequence) built.reverseProtectiveSequence = reverseProtectiveSequence;
  return built;
}

/**
 * The primer already on the bench to pair this design against.
 *
 * Only colony screening asks. Two primers inside the insert give the same band
 * whichever way round it went in, so pairing one insert primer against a
 * primer in the backbone is the only arrangement that answers the question
 * that assay exists to answer — and the field has been on the engine, and the
 * screen in the worker, since both were written, with nothing able to fill it.
 */
function vectorPrimerFrom(form: FormData): Record<string, string | number> | undefined {
  const name = field(form, "vectorPrimerName").trim();
  const sequence = field(form, "vectorPrimerSequence").trim();
  if (!name && !sequence) return undefined;

  const built: Record<string, string | number> = {};
  if (name) built.name = name;
  if (sequence) built.sequence = sequence;
  const side = field(form, "vectorPrimerReadsInto").trim();
  if (side) built.readsInto = side;
  // Optional, and what it buys is the product size: the vector primer sits
  // some distance from the cloning site, and that distance belongs to a
  // plasmid the worker has never seen. Without it the screen can only report
  // the half it controls, which is not the number a gel is read against.
  const plasmid = field(form, "vectorSequence").trim();
  if (plasmid) built.vector = plasmid;
  return built;
}

/**
 * A 5' addition that belongs to a downstream step rather than to the template.
 *
 * Distinct from `tailsFrom`, which builds restriction sites out of two enzyme
 * names. This one is whatever somebody typed: a sequencing adapter or a
 * universal-primer tail, fixed by what happens after the PCR rather than by
 * anything this could work out.
 */
function fivePrimeTails(form: FormData): { forward?: string; reverse?: string } | undefined {
  const forward = field(form, "tailForward").trim();
  const reverse = field(form, "tailReverse").trim();
  if (!forward && !reverse) return undefined;
  return {
    ...(forward ? { forward } : {}),
    ...(reverse ? { reverse } : {}),
  };
}

/**
 * Adjustments to whichever LAMP parameter set is in force.
 *
 * Collected by prefix — `w_outer_tm_min`, `w_f2_b2_span_min` — for the same
 * reason the rounds and the constraints are: a second list of field names kept
 * beside the controls is a second place to be wrong.
 *
 * `undefined` when nothing was filled in, so a page that never asked sends
 * nothing at all rather than an empty block. The worker owns which fields
 * exist and what each is bounded by, and refuses anything else by name.
 */
export function requestFor(engine: string, template: string, form: FormData): DesignPayload {
  // What every engine takes: the sequence, what to call it, the reaction, and
  // what the primers have to satisfy.
  const lowercaseMaskingRaw = field(form, "lowercaseMasking");
  const lowercaseMasking =
    lowercaseMaskingRaw === "true" ? true : lowercaseMaskingRaw === "false" ? false : undefined;
  const common: DesignPayload = {
    template,
    lowercaseMasking,
    name: field(form, "name") || undefined,
    polymerase: field(form, "polymerase") || undefined,
    purpose: field(form, "purpose") || undefined,
    constraints: constraintsFrom(form),
  };

  /*
   * Only where the assay declares it.
   *
   * The page asks the question for the eight assays that carry the
   * reverse-transcription modifier and for no others, so an absent answer here
   * means the question was never put — not that it was answered "no".
   */
  const fromRnaRaw = field(form, "fromRna");
  const fromRna =
    fromRnaRaw === "true" ? { fromRna: true } : fromRnaRaw === "false" ? { fromRna: false } : {};

  // Only the shared flanking-pair engine owns this transcript geometry field.
  // Sending it to another engine would be an unknown-field error by design.
  const transcript = engine === "flanking-pair" ? { exonJunctions: exonJunctionsFrom(form) } : {};

  /*
   * Same shape, same reason: only the eight assays whose plan asks it send it,
   * and an absent answer means the question was never put rather than "no".
   */
  const circularRaw = field(form, "circular");
  const circular =
    circularRaw === "true"
      ? { circular: true }
      : circularRaw === "false"
        ? { circular: false }
        : {};

  const target = {
    // Through the converter, like every other coordinate here. A length is not
    // a coordinate and is not converted: ten bases are ten bases in any frame.
    targetStart: zeroBased(optionalNumber(form, "targetStart")),
    targetLength: optionalNumber(form, "targetLength"),
  };
  const howMany = { howMany: optionalNumber(form, "howMany") };

  switch (engine) {
    case "pair-and-probe":
      return {
        ...common,
        ...fromRna,
        ...circular,
        ...target,
        ...howMany,
        excluded: excludedFrom(form),
        background: field(form, "background") || undefined,
        probe: roundFrom(form, "probe"),
        probeProtocol: currentProbeProtocol(form),
        probeChemistry:
          (field(form, "probeChemistry") as DesignPayload["probeChemistry"]) || undefined,
        probeReporter: field(form, "probeReporter") || undefined,
        probeQuencher: field(form, "probeQuencher") || undefined,
        probeInternalQuencher: field(form, "probeInternalQuencher") || undefined,
        probeInstrumentProfile: field(form, "probeInstrumentProfile") || undefined,
        probeTranscriptMode:
          (field(form, "probeTranscriptMode") as DesignPayload["probeTranscriptMode"]) || undefined,
        ...probeClosureFields(form),
        workflowEvidence: workflowEvidenceFrom(form, "qpcr-probe"),
      };

    // Placement is the design here, so the target is not optional — the engine
    // says so itself rather than defaulting to the middle of the template.
    case "single-primer":
      return {
        ...common,
        ...circular,
        ...target,
        ...howMany,
        excluded: excludedFrom(form),
        background: field(form, "background") || undefined,
        ...(field(form, "moduleId") !== "race"
          ? {
              direction: (field(form, "direction") as DesignPayload["direction"]) || undefined,
            }
          : {}),
        ...(field(form, "moduleId") === "sequencing-primer"
          ? {
              deadZone: optionalNumber(form, "deadZone"),
              readLength: optionalNumber(form, "readLength"),
              sequencingProtocol:
                (field(form, "sequencingProtocol") as DesignPayload["sequencingProtocol"]) ||
                undefined,
              sequencingDesignProfile:
                (field(
                  form,
                  "sequencingDesignProfile",
                ) as DesignPayload["sequencingDesignProfile"]) || undefined,
              sequencingProvider: field(form, "sequencingProvider").trim() || undefined,
              sequencingUniversalPrimerScan:
                field(form, "sequencingUniversalPrimerScan") === "true",
              sequencingBidirectional: field(form, "sequencingBidirectional") === "true",
              sequencingInstrument:
                (field(form, "sequencingInstrument") as DesignPayload["sequencingInstrument"]) ||
                "unresolved",
              sequencingInstrumentName:
                (field(form, "sequencingInstrument") || "unresolved") === "other"
                  ? field(form, "sequencingInstrumentName").trim() || undefined
                  : undefined,
              sequencingFacilitySop: field(form, "sequencingFacilitySop").trim() || undefined,
            }
          : {}),
        ...(field(form, "moduleId") === "race"
          ? {
              raceDirection:
                (field(form, "raceDirection") as DesignPayload["raceDirection"]) || undefined,
              raceChemistry:
                (field(form, "raceChemistry") as DesignPayload["raceChemistry"]) || undefined,
              raceAdapter:
                (field(form, "raceAdapter") as DesignPayload["raceAdapter"]) || undefined,
              racePartnerSequence:
                ["custom", "smarter-race-current"].includes(field(form, "raceAdapter")) ||
                ["custom", "smarter-race-current"].includes(field(form, "raceChemistry"))
                  ? field(form, "racePartnerSequence") || undefined
                  : undefined,
              raceSopRevision: ["custom", "smarter-race-current"].includes(
                field(form, "raceChemistry"),
              )
                ? field(form, "raceSopRevision").trim() || undefined
                : undefined,
              raceSopSha256: ["custom", "smarter-race-current"].includes(
                field(form, "raceChemistry"),
              )
                ? field(form, "raceSopSha256").trim().toLowerCase() || undefined
                : undefined,
              raceSubstrate:
                (field(form, "raceSubstrate") as DesignPayload["raceSubstrate"]) || undefined,
              racePreparation: field(form, "racePreparation").trim() || undefined,
              raceRound: (field(form, "raceRound") as DesignPayload["raceRound"]) || undefined,
            }
          : {}),
        ...singleClosureFields(form, field(form, "moduleId")),
        workflowEvidence: workflowEvidenceFrom(form, field(form, "moduleId")),
      };

    // Told what to change rather than where to amplify.
    case "mutagenic-pair":
      return {
        ...common,
        ...howMany,
        edit: editFrom(form),
        edits: editsFrom(form),
        mutagenesisTopology:
          (field(form, "mutagenesisTopology") as DesignPayload["mutagenesisTopology"]) || undefined,
        aminoAcidEdit: aminoAcidEditFrom(form),
        codonPolicy: (field(form, "codonPolicy") as DesignPayload["codonPolicy"]) || undefined,
        codonUsage: jsonRecordNumberFrom(form, "codonUsage", "Codon usage"),
        libraryMode: mutagenesisLibraryModeFrom(form),
        libraryEdit: libraryEditFrom(form),
        templateMethylationStatus:
          (field(
            form,
            "templateMethylationStatus",
          ) as DesignPayload["templateMethylationStatus"]) || undefined,
        postAmplificationProtocol:
          (field(
            form,
            "postAmplificationProtocol",
          ) as DesignPayload["postAmplificationProtocol"]) || undefined,
        workflowEvidence: workflowEvidenceFrom(form, "site-directed-mutagenesis"),
      };

    // Covers everything, so there is no region to be given; and its pools are
    // a property of the whole scheme rather than of any one pair, so it has no
    // "how many" either.
    case "tiling-scheme": {
      const tilingOperation =
        (field(form, "tilingOperation") as DesignPayload["tilingOperation"]) || undefined;
      return {
        ...common,
        ...tilingClosureFields(form),
        excluded: excludedFrom(form),
        tilingBackend:
          (field(form, "tilingBackend") as DesignPayload["tilingBackend"]) || undefined,
        tilingMinBaseFrequency: optionalNumber(form, "tilingMinBaseFrequency"),
        tilingBacktrack: field(form, "tilingBacktrack") === "true",
        tilingHighGc: field(form, "tilingHighGc") === "true",
        olivarSeed: optionalNumber(form, "olivarSeed"),
        olivarDegenerateMode: field(form, "olivarDegenerateMode") === "true",
        olivarCheckVariants: field(form, "olivarCheckVariants") !== "false",
        schemeVersion: field(form, "schemeVersion") || undefined,
        workflowEvidence: workflowEvidenceFrom(form, "tiled-scheme"),
        overlap: tilingOperation === "scheme-create" ? optionalNumber(form, "overlap") : undefined,
        pools:
          tilingOperation === "scheme-create" || tilingOperation === "panel-create"
            ? optionalNumber(form, "pools")
            : undefined,
        tilingOperation,
        tilingAlignmentMode:
          (field(form, "tilingAlignmentMode") as DesignPayload["tilingAlignmentMode"]) || undefined,
        existingBed:
          tilingOperation === "panel-create" ||
          tilingOperation === "repair-mode" ||
          tilingOperation === "scheme-replace"
            ? field(form, "existingBed") || undefined
            : undefined,
        schemeConfig:
          tilingOperation === "repair-mode" || tilingOperation === "scheme-replace"
            ? field(form, "schemeConfig") || undefined
            : undefined,
        regionBed:
          tilingOperation === "panel-create" ? field(form, "regionBed") || undefined : undefined,
        panelMode:
          tilingOperation === "panel-create"
            ? (field(form, "panelMode") as DesignPayload["panelMode"]) || undefined
            : undefined,
        primerName:
          tilingOperation === "scheme-replace" ? field(form, "primerName") || undefined : undefined,
      };
    }

    // Given a plan rather than a template, and a chemistry with no default.
    case "junction-primers": {
      /*
       * No template at all, not an empty one.
       *
       * This engine takes `segments` and has no `template` field, and it
       * refuses unknown ones — so `template: ""` was not an empty value being
       * ignored, it was `unknown field \`template\``, and every Gibson design
       * failed. Confirmed against the running core.
       *
       * `purpose` goes too: a plan is not a product, and there is nothing here
       * for a purpose to size.
       */
      const { template: _sequence, purpose: _use, ...withoutTemplate } = common;
      return {
        ...withoutTemplate,
        segments: segmentsFrom(form),
        circular:
          field(form, "circular") === "true"
            ? true
            : field(form, "circular") === "false"
              ? false
              : undefined,
        // The module contract fixes the release-executable branch. A stale draft
        // must not relabel a Gibson design as an unvalidated assembly chemistry.
        method: "gibson",
        // "assemblyMethod" is the browser-facing control; the canonical wire
        // field is `method`, so it is normalized here rather than forwarded as
        // an extra worker key.
        // "assemblyProtocol" is the named browser overlay carried on the
        // canonical request below.
        assemblyProtocol: "neb-e5510",
        workflowEvidence: workflowEvidenceFrom(form, "gibson-assembly"),
      };
    }

    // Anchored on one base, and both alleles are required.
    case "discriminating-pair":
      return {
        ...common,
        at: zeroBased(optionalNumber(form, "at")),
        alleles: allelesFrom(form),
        variant: variantFrom(form),
        nearbyVariantsVcf: field(form, "nearbyVariantsVcf").trim() || undefined,
        mismatchEvidenceProfile: field(form, "mismatchEvidenceProfile").trim() || undefined,
        geometry: field(form, "geometry") || undefined,
        tetraMinBandSeparationBp:
          field(form, "geometry") === "tetra"
            ? optionalNumber(form, "tetraMinBandSeparationBp")
            : undefined,
        tetraReadout:
          field(form, "geometry") === "tetra"
            ? (field(form, "tetraReadout") as DesignPayload["tetraReadout"]) || undefined
            : undefined,
        tetraGelPercent:
          field(form, "geometry") === "tetra" ? optionalNumber(form, "tetraGelPercent") : undefined,
        tetraLadder:
          field(form, "geometry") === "tetra"
            ? field(form, "tetraLadder").trim() || undefined
            : undefined,
        tetraRunContext:
          field(form, "geometry") === "tetra"
            ? field(form, "tetraRunContext").trim() || undefined
            : undefined,
        kaspProtocol:
          field(form, "geometry") === "kasp"
            ? (field(form, "kaspProtocol") as DesignPayload["kaspProtocol"]) || undefined
            : undefined,
        kaspAssayMode:
          field(form, "geometry") === "kasp"
            ? ((field(form, "kaspAssayMode") || undefined) as DesignPayload["kaspAssayMode"])
            : undefined,
        kaspPlateFormat:
          field(form, "geometry") === "kasp" &&
          ["lgc-standard", "lgc-kasp-tf-v5"].includes(field(form, "kaspProtocol"))
            ? ((field(form, "kaspPlateFormat") || undefined) as DesignPayload["kaspPlateFormat"])
            : undefined,
        kaspInstrumentModel:
          field(form, "geometry") === "kasp" &&
          ["lgc-standard", "lgc-kasp-tf-v5"].includes(field(form, "kaspProtocol"))
            ? field(form, "kaspInstrumentModel") || undefined
            : undefined,
        kaspRoxPolicy:
          field(form, "geometry") === "kasp" &&
          ["lgc-standard", "lgc-kasp-tf-v5"].includes(field(form, "kaspProtocol"))
            ? (field(form, "kaspRoxPolicy") as DesignPayload["kaspRoxPolicy"]) || undefined
            : undefined,
        background: field(form, "background") || undefined,
        excluded: excludedFrom(form),
        workflowEvidence: workflowEvidenceFrom(form, field(form, "moduleId")),
      };

    // Held to three windows at once, chosen from the template unless named.
    case "loop-set": {
      /*
       * Everything in `common` except the constraints.
       *
       * This engine has no constraint block at all — the geometry is set by the
       * window set — and it refuses unknown fields, so a value left in the
       * draft from before the constraints step was removed from this page would
       * turn the run into an error rather than being ignored.
       */
      const { constraints: _unused, ...withoutConstraints } = common;
      return {
        ...withoutConstraints,
        ...fromRna,
        ...circular,
        ...howMany,
        background: field(form, "background") || undefined,
        inclusivity: field(form, "inclusivity") || undefined,
        excluded: excludedFrom(form),
        parameterSet: field(form, "parameterSet") || undefined,
        lampGeometryProfile:
          (field(form, "lampGeometryProfile") as DesignPayload["lampGeometryProfile"]) || undefined,
        lampInnerLinker:
          (field(form, "lampInnerLinker") as DesignPayload["lampInnerLinker"]) || undefined,
        lampProtocol: (field(form, "lampProtocol") as DesignPayload["lampProtocol"]) || undefined,
        lampReadout: (field(form, "lampReadout") as DesignPayload["lampReadout"]) || undefined,
        lampReadoutChemistry:
          (field(form, "lampReadoutChemistry") as DesignPayload["lampReadoutChemistry"]) ||
          undefined,
        lampSampleMatrix:
          (field(form, "lampSampleMatrix") as DesignPayload["lampSampleMatrix"]) || undefined,
        lampSamplePreparation:
          (field(form, "lampSamplePreparation") as DesignPayload["lampSamplePreparation"]) ||
          undefined,
        lampFormulation:
          (field(form, "lampFormulation") as DesignPayload["lampFormulation"]) || undefined,
        lampConfirmationMode:
          (field(form, "lampConfirmationMode") as DesignPayload["lampConfirmationMode"]) ||
          undefined,
        lampDetectionTopology:
          (field(form, "lampDetectionTopology") as DesignPayload["lampDetectionTopology"]) ||
          undefined,
        lampMultiplexPlan: jsonArrayObjectFrom(
          form,
          "lampMultiplexPlan",
          "LAMP multiplex plan",
        ) as DesignPayload["lampMultiplexPlan"],
        lampDesignIntent:
          (field(form, "lampDesignIntent") as DesignPayload["lampDesignIntent"]) || undefined,
        lampDesignStage:
          (field(form, "lampDesignStage") as DesignPayload["lampDesignStage"]) || undefined,
        lampFixedPrimers: (() => {
          const values = Object.fromEntries(
            (["F3", "B3", "FIP", "BIP", "LF", "LB"] as const).flatMap((role) => {
              const sequence = field(form, `lampFixed${role}`).trim();
              return sequence ? [[role, sequence.toUpperCase()]] : [];
            }),
          ) as DesignPayload["lampFixedPrimers"];
          return values && Object.keys(values).length ? values : undefined;
        })(),
        lampVariant: (() => {
          if (field(form, "lampDesignIntent") !== "mutation-anchored-specific") return undefined;
          const position = optionalNumber(form, "lampVariantPosition");
          const ref = field(form, "lampVariantRef").trim().toUpperCase();
          const alt = field(form, "lampVariantAlt").trim().toUpperCase();
          const anchor = field(form, "lampVariantAnchor") as NonNullable<
            DesignPayload["lampVariant"]
          >["anchor"];
          return position === undefined || !ref || !alt || !anchor
            ? undefined
            : { position, ref, alt, anchor };
        })(),
        lampLoopPolicy:
          (field(form, "lampLoopPolicy") as DesignPayload["lampLoopPolicy"]) || undefined,
        lampCarryoverStrategy:
          (field(form, "lampCarryoverStrategy") as DesignPayload["lampCarryoverStrategy"]) ||
          undefined,
        lampReconstitutionX:
          (field(form, "lampReconstitutionX") as DesignPayload["lampReconstitutionX"]) || undefined,
        lampSpecificityAdditive:
          (field(form, "lampSpecificityAdditive") as DesignPayload["lampSpecificityAdditive"]) ||
          undefined,
        lampAccelerationAdditive:
          (field(form, "lampAccelerationAdditive") as DesignPayload["lampAccelerationAdditive"]) ||
          undefined,
        lampPrimerKineticsProfile:
          (field(
            form,
            "lampPrimerKineticsProfile",
          ) as DesignPayload["lampPrimerKineticsProfile"]) || undefined,
        lampPreincubationStrategy:
          (field(
            form,
            "lampPreincubationStrategy",
          ) as DesignPayload["lampPreincubationStrategy"]) || undefined,
        lampSampleBufferType:
          (field(form, "lampSampleBufferType") as DesignPayload["lampSampleBufferType"]) ||
          undefined,
        lampInstrumentProfile:
          (field(form, "lampInstrumentProfile") as DesignPayload["lampInstrumentProfile"]) ||
          undefined,
        lampSampleInputPercent: optionalNumber(form, "lampSampleInputPercent"),
        lampSampleBufferPh: optionalNumber(form, "lampSampleBufferPh"),
        lampSampleBufferPercent: optionalNumber(form, "lampSampleBufferPercent"),
        lampTransportMediumPercent: optionalNumber(form, "lampTransportMediumPercent"),
        lampBileSaltMgMl: optionalNumber(form, "lampBileSaltMgMl"),
        lampCaryBlairPercent: optionalNumber(form, "lampCaryBlairPercent"),
        lampUpstreamGuanidineMm: optionalNumber(form, "lampUpstreamGuanidineMm"),
        lampBenchOptimization: (() => {
          const values: Record<string, number> = {};
          for (const [wire, key] of LAMP_BENCH_FIELD_MAP) {
            const parsed = optionalNumber(form, wire);
            if (parsed !== undefined) values[key] = parsed;
          }
          return Object.keys(values).length ? values : undefined;
        })(),
        mode: field(form, "assayMode") === "evaluate" ? "validate-existing" : "design",
        ...(field(form, "assayMode") === "evaluate"
          ? {
              existingSet: {
                f3: field(form, "existingLampF3").trim(),
                b3: field(form, "existingLampB3").trim(),
                fip: field(form, "existingLampFip").trim(),
                bip: field(form, "existingLampBip").trim(),
                ...(field(form, "existingLampLf").trim()
                  ? { lf: field(form, "existingLampLf").trim() }
                  : {}),
                ...(field(form, "existingLampLb").trim()
                  ? { lb: field(form, "existingLampLb").trim() }
                  : {}),
                fipF1cLength: optionalNumber(form, "existingLampFipF1cLength") ?? 0,
                bipB1cLength: optionalNumber(form, "existingLampBipB1cLength") ?? 0,
              },
            }
          : {}),
        workflowEvidence: workflowEvidenceFrom(form, "lamp"),
        windows: windowsFromDraft(form),
      };
    }

    case "outward-pair":
      return {
        ...common,
        ...howMany,
        ...outwardClosureFields(form),
        background: field(form, "background") || undefined,
        circleLength: optionalNumber(form, "circleLength"),
        enzyme: field(form, "enzyme") || undefined,
        inverseBranch:
          (field(form, "inverseBranch") as DesignPayload["inverseBranch"]) || undefined,
        enzymeCohortSize: optionalNumber(form, "enzymeCohortSize"),
        mappingUseCase:
          (field(form, "mappingUseCase") as DesignPayload["mappingUseCase"]) || undefined,
        leftEndPhosphate:
          (field(form, "leftEndPhosphate") as DesignPayload["leftEndPhosphate"]) || undefined,
        rightEndPhosphate:
          (field(form, "rightEndPhosphate") as DesignPayload["rightEndPhosphate"]) || undefined,
        circularizationProvenance: field(form, "circularizationProvenance") || undefined,
        linearControlProvenance: field(form, "linearControlProvenance") || undefined,
        methylationBranch: field(form, "methylationBranch") || undefined,
        unknownFlankMin: optionalNumber(form, "unknownFlankMin"),
        unknownFlankMax: optionalNumber(form, "unknownFlankMax"),
        workflowEvidence: workflowEvidenceFrom(form, "inverse-pcr"),
      };

    case "nested": {
      /*
       * The two round windows replace the shared constraint block, but nested
       * still accepts specificity and avoided regions. Both are sent below so
       * the outer and inner searches are judged against the stated sample and
       * exclusions.
       */
      // `constraints` is not sent: this engine sets each round's limits from
      // `outer` and `inner`, while still accepting the shared scan inputs.
      const { constraints: _unused, ...withoutConstraints } = common;
      return {
        ...withoutConstraints,
        ...fromRna,
        ...target,
        ...howMany,
        excluded: excludedFrom(form),
        background: field(form, "background") || undefined,
        outer: roundFrom(form, "outer"),
        inner: roundFrom(form, "inner"),
        shares: (field(form, "shares") as DesignPayload["shares"]) || undefined,
        margin: optionalNumber(form, "margin"),
        singleTube:
          field(form, "singleTube") === "true"
            ? true
            : field(form, "singleTube") === "false"
              ? false
              : undefined,
        carryoverPrevention:
          (field(form, "carryoverPrevention") as DesignPayload["carryoverPrevention"]) || undefined,
        transferMode: (field(form, "transferMode") as DesignPayload["transferMode"]) || undefined,
        cleanupProtocol:
          (field(form, "cleanupProtocol") as DesignPayload["cleanupProtocol"]) || undefined,
        transferVolumeUl: optionalNumber(form, "transferVolumeUl"),
        transferDilutionFactor: optionalNumber(form, "transferDilutionFactor"),
        customTransferSop: field(form, "customTransferSop").trim() || undefined,
        round1Polymerase: field(form, "round1Polymerase").trim() || undefined,
        round2Polymerase: field(form, "round2Polymerase").trim() || undefined,
        round1Conditions: jsonRecordNumberFrom(form, "round1Conditions", "Round 1 conditions"),
        round2Conditions: jsonRecordNumberFrom(form, "round2Conditions", "Round 2 conditions"),
        round1ThermalProgram: jsonArrayObjectFrom(
          form,
          "round1ThermalProgram",
          "Round 1 thermal program",
        ),
        round2ThermalProgram: jsonArrayObjectFrom(
          form,
          "round2ThermalProgram",
          "Round 2 thermal program",
        ),
        workflowEvidence: workflowEvidenceFrom(form, "nested-pcr"),
      };
    }

    case "consensus-pair": {
      /*
       * An alignment, and nothing about a region in it.
       *
       * This had no branch at all, so it fell through to the amplification
       * shape and sent five fields the engine refuses — `background`,
       * `excluded`, `targetStart`, `targetLength` and `purpose`. A degenerate
       * pair is designed from what a family shares; there is no single
       * template to point at and no background to be silent on.
       */
      const { purpose: _unused, ...withoutPurpose } = common;
      return {
        ...withoutPurpose,
        ...fromRna,
        ...howMany,
        tails: fivePrimeTails(form),
        alignmentMode:
          (field(form, "alignmentMode") as DesignPayload["alignmentMode"]) || undefined,
        consensusPolicy:
          (field(form, "consensusPolicy") as DesignPayload["consensusPolicy"]) ||
          "strict-all-members",
        panelMetadata: (() => {
          const raw = field(form, "panelMetadata").trim();
          if (!raw) return undefined;
          try {
            return JSON.parse(raw) as DesignPayload["panelMetadata"];
          } catch {
            throw new Error("Panel metadata must be valid JSON keyed by FASTA record id.");
          }
        })(),
        formulationMode:
          (field(form, "formulationMode") as DesignPayload["formulationMode"]) ||
          "mixed-base-synthesis",
        formulationTotalConcentrationNm: optionalNumber(form, "formulationTotalConcentrationNm"),
        nontarget: field(form, "nontarget").trim() || undefined,
        alternativeAlignment: field(form, "alternativeAlignment").trim() || undefined,
        alignmentAuditBackend: field(form, "alignmentAuditBackend").trim() || undefined,
        workflowEvidence: workflowEvidenceFrom(form, "universal-primers"),
      };
    }

    default:
      return {
        ...common,
        ...fromRna,
        ...transcript,
        ...circular,
        ...target,
        ...howMany,
        tails: tailsFrom(form),
        vectorPrimer: vectorPrimerFrom(form),
        ...(field(form, "moduleId") === "restriction-cloning"
          ? {
              cloningVector: field(form, "cloningVector").trim() || undefined,
              cloningVectorName: field(form, "cloningVectorName").trim() || undefined,
              cloningVectorTopology:
                (field(form, "cloningVectorTopology") as DesignPayload["cloningVectorTopology"]) ||
                undefined,
              restrictionDigestProtocol:
                (field(
                  form,
                  "restrictionDigestProtocol",
                ) as DesignPayload["restrictionDigestProtocol"]) || undefined,
              restrictionDephosphorylationProtocol:
                (field(
                  form,
                  "restrictionDephosphorylationProtocol",
                ) as DesignPayload["restrictionDephosphorylationProtocol"]) || undefined,
              restrictionLigationProtocol:
                (field(
                  form,
                  "restrictionLigationProtocol",
                ) as DesignPayload["restrictionLigationProtocol"]) || undefined,
              cloningCodingIntent:
                (field(form, "cloningCodingIntent") as DesignPayload["cloningCodingIntent"]) ||
                "noncoding",
              cloningCdsStart: optionalNumber(form, "cloningCdsStart"),
              cloningCdsEnd: optionalNumber(form, "cloningCdsEnd"),
              cloningStopCodonPolicy:
                (field(
                  form,
                  "cloningStopCodonPolicy",
                ) as DesignPayload["cloningStopCodonPolicy"]) || "not-applicable",
              cloningFusionTag: field(form, "cloningFusionTag").trim() || undefined,
              cloningLinkerAa: field(form, "cloningLinkerAa").trim() || undefined,
              cloningVectorJunctionFrame: optionalNumber(form, "cloningVectorJunctionFrame") as
                0 | 1 | 2 | undefined,
            }
          : {}),
        workflowEvidence: workflowEvidenceFrom(form, field(form, "moduleId")),
        flankingNumericContext: flankingNumericContextFromDraft(form, field(form, "moduleId")),
        ...(field(form, "moduleId") === "colony-pcr"
          ? {
              colonyHostClass:
                (field(form, "colonyHostClass") as DesignPayload["colonyHostClass"]) || undefined,
              colonyPreparation:
                (field(form, "colonyPreparation") as DesignPayload["colonyPreparation"]) ||
                undefined,
              colonyProtocolId:
                (field(form, "colonyProtocolId") as DesignPayload["colonyProtocolId"]) || undefined,
              colonyProtocolName: field(form, "colonyProtocolName").trim() || undefined,
              colonyProtocolProvenance: field(form, "colonyProtocolProvenance").trim() || undefined,
            }
          : {}),
        background: field(form, "background") || undefined,
        ...(field(form, "moduleId") === "species-specific-pcr"
          ? {
              inclusivity: field(form, "inclusivity") || undefined,
              inclusivityPanelProvenance:
                field(form, "inclusivityPanelProvenance").trim() || undefined,
              backgroundPanelProvenance:
                field(form, "backgroundPanelProvenance").trim() || undefined,
              speciesPanelSelectionRationale:
                field(form, "speciesPanelSelectionRationale").trim() || undefined,
              speciesTargetTaxid: optionalNumber(form, "speciesTargetTaxid"),
              speciesTaxonomySnapshot: field(form, "speciesTaxonomySnapshot").trim() || undefined,
              speciesDatabaseSnapshot: field(form, "speciesDatabaseSnapshot").trim() || undefined,
              speciesPanelAccessionManifest:
                field(form, "speciesPanelAccessionManifest").trim() || undefined,
              speciesPanelAccessionAuthorityManifest:
                field(form, "speciesPanelAccessionAuthorityManifest").trim() || undefined,
              speciesPanelRecordMetadataManifest:
                field(form, "speciesPanelRecordMetadataManifest").trim() || undefined,
              speciesPanelRetrievedDate:
                field(form, "speciesPanelRetrievedDate").trim() || undefined,
            }
          : {}),
        maxMismatches: optionalNumber(form, "maxMismatches"),
        excluded: excludedFrom(form),
        variants: variantsFrom(form),
        ...(field(form, "moduleId") === "standard-pcr"
          ? {
              standardPcrProtocol:
                (field(form, "standardPcrProtocol") as DesignPayload["standardPcrProtocol"]) ||
                undefined,
            }
          : {}),
        ...(field(form, "moduleId") === "qpcr-sybr"
          ? {
              qpcrProtocol:
                (field(form, "qpcrProtocol") as DesignPayload["qpcrProtocol"]) || undefined,
            }
          : {}),
        ...(field(form, "moduleId") === "rpa"
          ? {
              rpaProtocol:
                (field(form, "rpaProtocol") as DesignPayload["rpaProtocol"]) || undefined,
            }
          : {}),
        ...(field(form, "moduleId") === "rpa"
          ? {
              rpaMultiplexPanel: jsonArrayObjectFrom(
                form,
                "rpaMultiplexPanel",
                "RPA multiplex panel",
              ) as DesignPayload["rpaMultiplexPanel"],
            }
          : {}),
        ...(field(form, "moduleId") === "long-range-pcr"
          ? {
              longRangeProtocol:
                (field(form, "longRangeProtocol") as DesignPayload["longRangeProtocol"]) ||
                undefined,
            }
          : {}),
        ...(field(form, "moduleId") === "digital-pcr"
          ? {
              digitalProtocol:
                (field(form, "digitalProtocol") as DesignPayload["digitalProtocol"]) || undefined,
              digitalPartitionFormat:
                (field(
                  form,
                  "digitalPartitionFormat",
                ) as DesignPayload["digitalPartitionFormat"]) || undefined,
              digitalPlatformId:
                (field(form, "digitalPlatformId") as DesignPayload["digitalPlatformId"]) ||
                undefined,
              digitalPlatformName:
                field(form, "digitalPlatformId") === "other-validated"
                  ? field(form, "digitalPlatformName").trim() || undefined
                  : undefined,
              digitalInstrumentModel:
                (field(
                  form,
                  "digitalInstrumentModel",
                ) as DesignPayload["digitalInstrumentModel"]) || undefined,
              digitalFragmentationState:
                (field(
                  form,
                  "digitalFragmentationState",
                ) as DesignPayload["digitalFragmentationState"]) || undefined,
              digitalMultiplexMode:
                (field(form, "digitalMultiplexMode") as DesignPayload["digitalMultiplexMode"]) ||
                "none",
              digitalMultiplexPanel: jsonArrayObjectFrom(
                form,
                "digitalMultiplexPanel",
                "Digital multiplex panel",
              ) as DesignPayload["digitalMultiplexPanel"],
              digitalRunEvidence: (() => {
                const raw = field(form, "digitalRunEvidence");
                if (!raw) return undefined;
                let parsed: unknown;
                try {
                  parsed = JSON.parse(raw);
                } catch {
                  throw new Error("Digital run evidence must be valid JSON.");
                }
                if (!parsed || typeof parsed !== "object" || Array.isArray(parsed))
                  throw new Error("Digital run evidence must be a JSON object.");
                return parsed as Record<string, unknown>;
              })(),
            }
          : {}),
      };
  }
}

/**
 * The change a mutagenesis is being asked to make.
 *
 * Returned undefined when nothing was filled in, so the engine can refuse it by
 * name rather than the form inventing an edit nobody asked for.
 */
/**
 * The fragments to join, in the order they go in.
 *
 * Sent as one field holding a line per fragment — `name, kind, sequence` —
 * because a plan is a list of unknown length and a form is a flat map. Parsed
 * here rather than in the component so the shape the engine sees is decided in
 * one place.
 */
function segmentsFrom(form: FormData): DesignPayload["segments"] {
  const raw = field(form, "segments").trim();
  if (!raw) return undefined;

  if (raw.startsWith("[")) {
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch {
      throw new Error("Assembly fragments JSON is not valid JSON.");
    }
    if (!Array.isArray(parsed) || parsed.length < 2) {
      throw new Error("Assembly fragments JSON must contain at least two fragment objects.");
    }
    return parsed as DesignPayload["segments"];
  }

  const found = raw
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      const [name, kind, sequence, orientation, concentration, mass, volume] = line
        .split(",")
        .map((part) => part.trim());
      if (!kind)
        throw new Error(`Assembly fragment ${index + 1} needs an explicit production kind.`);
      if (!sequence) throw new Error(`Assembly fragment ${index + 1} needs a sequence.`);
      const numeric = (text?: string) => {
        if (!text) return undefined;
        const n = Number(text);
        if (!Number.isFinite(n) || n < 0)
          throw new Error(`Assembly fragment ${index + 1} has an invalid numeric metadata value.`);
        return n;
      };
      return {
        name,
        kind: kind as NonNullable<DesignPayload["segments"]>[number]["kind"],
        sequence,
        orientation: (orientation || undefined) as NonNullable<
          DesignPayload["segments"]
        >[number]["orientation"],
        concentrationNgUl: numeric(concentration),
        massNg: numeric(mass),
        volumeUl: numeric(volume),
      };
    });
  return found.length ? found : undefined;
}

function variantFrom(form: FormData): DesignPayload["variant"] {
  const kind = field(form, "variantType") as NonNullable<DesignPayload["variant"]>["type"];
  const at = zeroBased(optionalNumber(form, "variantAt") ?? optionalNumber(form, "at"));
  if (!kind || at === undefined) return undefined;
  return {
    type: kind,
    at,
    ref: field(form, "variantRef").trim().toUpperCase(),
    alt: field(form, "variantAlt").trim().toUpperCase(),
    referenceAccession: field(form, "variantReferenceAccession").trim() || undefined,
    assembly: field(form, "variantAssembly").trim() || undefined,
    coordinateSystem: field(form, "variantCoordinateSystem").trim() || "0-based-reference",
    strand: (field(form, "variantStrand") as "plus" | "minus") || "plus",
    rsid: field(form, "variantRsid").trim() || undefined,
  };
}

function jsonRecordNumberFrom(
  form: FormData,
  key: string,
  label: string,
): Record<string, number> | undefined {
  const raw = field(form, key).trim();
  if (!raw) return undefined;
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error(`${label} must be valid JSON.`);
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed))
    throw new Error(`${label} must be a JSON object.`);
  const out: Record<string, number> = {};
  for (const [name, value] of Object.entries(parsed as Record<string, unknown>)) {
    if (typeof value !== "number" || !Number.isFinite(value))
      throw new Error(`${label}.${name} must be a finite number.`);
    out[name] = value;
  }
  return out;
}

function jsonArrayObjectFrom(
  form: FormData,
  key: string,
  label: string,
): Array<Record<string, unknown>> | undefined {
  const raw = field(form, key).trim();
  if (!raw) return undefined;
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error(`${label} must be valid JSON.`);
  }
  if (
    !Array.isArray(parsed) ||
    parsed.some((item) => !item || typeof item !== "object" || Array.isArray(item))
  ) {
    throw new Error(`${label} must be a JSON array of stage objects.`);
  }
  return parsed as Array<Record<string, unknown>>;
}

function editsFrom(form: FormData): DesignPayload["edits"] {
  const raw = field(form, "editsJson").trim();
  if (!raw) return undefined;
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error("Multi-edit list must be valid JSON.");
  }
  if (!Array.isArray(parsed)) throw new Error("Multi-edit list must be a JSON array.");
  return parsed.map((item, index) => {
    if (!item || typeof item !== "object" || Array.isArray(item))
      throw new Error(`Edit ${index + 1} must be an object.`);
    const row = item as Record<string, unknown>;
    const atRaw = Number(row.at);
    if (!Number.isInteger(atRaw) || atRaw < 1)
      throw new Error(`Edit ${index + 1}.at must be a 1-based positive integer in the UI.`);
    return {
      kind: String(row.kind || ""),
      at: atRaw - 1,
      to: row.to == null ? undefined : String(row.to).toUpperCase(),
      replacing: row.replacing == null ? undefined : Number(row.replacing),
    };
  });
}

function aminoAcidEditFrom(form: FormData): DesignPayload["aminoAcidEdit"] {
  if (field(form, "editInputMode") !== "amino-acid") return undefined;
  const cdsStart = zeroBased(optionalNumber(form, "aaCdsStart"));
  const residue = optionalNumber(form, "aaResidue");
  const toAa = field(form, "aaTo").trim().toUpperCase();
  if (cdsStart === undefined || residue === undefined || !toAa) return undefined;
  return {
    cdsStart,
    residue,
    fromAa: field(form, "aaFrom").trim().toUpperCase() || undefined,
    toAa,
    codon: field(form, "aaCodon").trim().toUpperCase() || undefined,
  };
}

function libraryEditFrom(form: FormData): DesignPayload["libraryEdit"] {
  if (field(form, "editInputMode") !== "library") return undefined;
  const mode =
    field(form, "libraryMode") && field(form, "libraryMode") !== "none"
      ? field(form, "libraryMode")
      : "NNK";
  const at = zeroBased(optionalNumber(form, "libraryAt"));
  if (at === undefined) return undefined;
  const codon = mode === "custom" ? field(form, "libraryCodon").trim().toUpperCase() : mode;
  return { at, codon };
}

function mutagenesisLibraryModeFrom(form: FormData): DesignPayload["libraryMode"] {
  if (field(form, "editInputMode") !== "library") return "none";
  const mode = field(form, "libraryMode");
  return (mode && mode !== "none" ? mode : "NNK") as DesignPayload["libraryMode"];
}

/** The two alleles, which are two fields rather than a list in the form. */
function allelesFrom(form: FormData): string[] | undefined {
  const one = field(form, "alleleOne").trim();
  const other = field(form, "alleleTwo").trim();
  return one && other ? [one, other] : undefined;
}

function editFrom(form: FormData): DesignPayload["edit"] {
  const kind = field(form, "editKind");
  const at = zeroBased(optionalNumber(form, "editAt"));
  if (!kind || at === undefined) return undefined;
  return {
    kind,
    at,
    to:
      kind === "substitute" || kind === "insert"
        ? field(form, "editTo").toUpperCase() || undefined
        : undefined,
    replacing:
      kind === "substitute" || kind === "delete"
        ? optionalNumber(form, "editReplacing")
        : undefined,
  };
}

import type { EngineId } from "@/lib/api/types";
import type { ValidationIssue } from "@/lib/contracts/validation-issue";
import { hasBlockingIssue } from "@/lib/contracts/validation-issue";
import { resolveFlankingNumericPreview, type FlankingModuleId } from "@/lib/flanking-contract";
import {
  LAMP_BENCH_FIELD_MAP,
  lampScenarioIssueOwner,
  lampScenarioIssues,
} from "@/lib/lamp-contract";
import type { RawDraftValues } from "@/lib/projects/draft";
import {
  requiredContextIssues,
  requiredDraftFields,
  requiredDraftFieldsForStep,
  type RequiredContextStep,
} from "@/lib/projects/required-context";
import { approximateBases, nucleotideSequenceForCase } from "@/components/design/approximate-bases";
import type { StepId } from "@/components/design/page-plan";

type Draft = RawDraftValues;

export const EXISTING_PAIR_EVALUATION_MODULES = new Set([
  "standard-pcr",
  "long-range-pcr",
  "colony-pcr",
  "qpcr-sybr",
  "digital-pcr",
  "rpa",
]);

const FLANKING_NUMERIC_MODULES = new Set([
  "standard-pcr",
  "long-range-pcr",
  "colony-pcr",
  "qpcr-sybr",
  "digital-pcr",
  "rpa",
]);

function text(draft: Draft, key: string): string {
  return draft[key] ?? "";
}

function flankingProtocolFor(moduleId: string, draft: Draft): string {
  switch (moduleId) {
    case "standard-pcr":
      return text(draft, "standardPcrProtocol");
    case "long-range-pcr":
      return text(draft, "longRangeProtocol");
    case "qpcr-sybr":
      return text(draft, "qpcrProtocol");
    case "digital-pcr":
      return text(draft, "digitalProtocol");
    case "rpa":
      return text(draft, "rpaProtocol");
    default:
      return "not-selected";
  }
}

function workflowRequirementsFor(
  moduleId: string,
  draft: Draft,
  colonyVectorPrimerRequired: boolean,
): string[] {
  if (moduleId === "restriction-cloning") {
    return [
      "cloningVector",
      "forwardEnzyme",
      "reverseEnzyme",
      "forwardProtectiveSequence",
      "reverseProtectiveSequence",
    ];
  }
  if (moduleId === "lamp" && text(draft, "assayMode") === "evaluate") {
    return [
      "existingLampF3",
      "existingLampB3",
      "existingLampFip",
      "existingLampBip",
      "existingLampFipF1cLength",
      "existingLampBipB1cLength",
    ];
  }
  return colonyVectorPrimerRequired
    ? ["vectorSequence", "vectorPrimerSequence", "vectorPrimerReadsInto"]
    : [];
}

export interface WorkspaceReadiness {
  bases: number;
  segments: number;
  missingRequirements: string[];
  readinessIssues: ValidationIssue[];
  runReady: boolean;
  done: Record<StepId, boolean>;
}

/**
 * Pure readiness projection for one draft.
 *
 * The component renders the result of this function; it does not own a second
 * implementation of scientific/workflow readiness. Keeping this pure also
 * lets regression tests exercise every module without mounting the workspace.
 */
export function workspaceReadiness({
  draft,
  engine,
  moduleId,
  requirements,
}: {
  draft: Draft;
  engine: EngineId;
  moduleId: string;
  requirements: readonly string[];
}): WorkspaceReadiness {
  const templateText = text(draft, "template");
  const bases = approximateBases(templateText);
  const hasLowercaseNucleotide = /[acgturyswkmbdhvn]/.test(nucleotideSequenceForCase(templateText));
  const lowercaseDecisionReady =
    !hasLowercaseNucleotide || ["true", "false"].includes(text(draft, "lowercaseMasking"));
  const polymerase = text(draft, "polymerase");
  const isAssembly = engine === "junction-primers";
  const segments = text(draft, "segments")
    .split("\n")
    .filter((line) => line.trim()).length;
  const designInputReady = isAssembly ? segments > 0 : bases > 0 && lowercaseDecisionReady;
  const reactionReady = isAssembly ? Boolean(text(draft, "method")) : Boolean(polymerase);
  const requiredFields = Array.from(
    new Set([...requirements, ...requiredDraftFields(moduleId, draft)]),
  );

  const targetStartGiven = Boolean(text(draft, "targetStart").trim());
  const targetLengthGiven = Boolean(text(draft, "targetLength").trim());
  const incompleteTargetPair =
    targetStartGiven === targetLengthGiven
      ? []
      : [targetStartGiven ? "targetLength" : "targetStart"];

  const colonyStrategy = text(draft, "colonyScreenStrategy") || "insert-specific-pair";
  const colonyVectorPrimerRequired =
    moduleId === "colony-pcr" &&
    ["vector-plus-insert", "orientation-screen"].includes(colonyStrategy);
  const unsupportedColonyStrategy =
    moduleId === "colony-pcr" && colonyStrategy === "two-vector-primers";

  const lampScenarioConflicts =
    moduleId === "lamp"
      ? lampScenarioIssues({
          protocol: text(draft, "lampProtocol"),
          fromRna: text(draft, "fromRna") === "true",
          matrix: text(draft, "lampSampleMatrix") || "not-specified",
          preparation: text(draft, "lampSamplePreparation") || "not-specified",
          formulation: text(draft, "lampFormulation") || "not-specified",
          readout: text(draft, "lampReadout") || "not-specified",
          chemistry: text(draft, "lampReadoutChemistry") || "not-specified",
          designIntent: text(draft, "lampDesignIntent") || "standard",
          inclusivity: text(draft, "inclusivity"),
          benchValues: Object.fromEntries(
            LAMP_BENCH_FIELD_MAP.map(([wire]) => [wire, text(draft, wire)]),
          ),
          carryoverStrategy: text(draft, "lampCarryoverStrategy") || "protocol-default",
          reconstitutionX: text(draft, "lampReconstitutionX") || "protocol-default",
          specificityAdditive: text(draft, "lampSpecificityAdditive") || "none",
          accelerationAdditive: text(draft, "lampAccelerationAdditive") || "none",
          primerKineticsProfile: text(draft, "lampPrimerKineticsProfile") || "protocol-default",
          preincubationStrategy: text(draft, "lampPreincubationStrategy") || "protocol-default",
          sampleInputPercent: text(draft, "lampSampleInputPercent"),
          sampleBufferType: text(draft, "lampSampleBufferType") || "none",
          sampleBufferPh: text(draft, "lampSampleBufferPh"),
          sampleBufferPercent: text(draft, "lampSampleBufferPercent"),
          transportMediumPercent: text(draft, "lampTransportMediumPercent"),
          bileSaltMgMl: text(draft, "lampBileSaltMgMl"),
          caryBlairPercent: text(draft, "lampCaryBlairPercent"),
          upstreamGuanidineMm: text(draft, "lampUpstreamGuanidineMm"),
          instrumentProfile: text(draft, "lampInstrumentProfile") || "not-specified",
        })
      : [];
  const lampScenarioMissing = lampScenarioConflicts.map((issue) => issue.field);

  const flankingNumericPreview = FLANKING_NUMERIC_MODULES.has(moduleId)
    ? resolveFlankingNumericPreview({
        moduleId: moduleId as FlankingModuleId,
        protocol: flankingProtocolFor(moduleId, draft) || "not-selected",
        reactionVolumeUl: text(draft, "flankingReactionVolumeUl"),
        primerEachUm: text(draft, "flankingPrimerEachUm"),
        primerEachNm: text(draft, "flankingPrimerEachNm"),
        gcEnhancerPercent: text(draft, "flankingGcEnhancerPercent"),
        additive: text(draft, "flankingAdditive"),
        cyclingProfile: text(draft, "qpcrCyclingProfile"),
        templateFractionPercent: text(draft, "flankingTemplateFractionPercent"),
        targetLengthKb: text(draft, "longRangeTargetLengthKb"),
        partitionFormatDetail: text(draft, "digitalPartitionFormatDetail"),
        preparation:
          moduleId === "colony-pcr"
            ? text(draft, "colonyPreparation")
            : text(draft, "flankingPreparation"),
        initialDenaturationTimeMin: text(draft, "colonyInitialDenaturationMin"),
        rpaTemperatureC: text(draft, "rpaTemperatureC"),
        rpaTimeMin: text(draft, "rpaTimeMin"),
        rpaBstUnitsPerUl: text(draft, "rpaBstUnitsPerUl"),
        rpaMultiplex: text(draft, "rpaMultiplex") === "true",
        templateInputNg: text(draft, "flankingTemplateInputNg"),
        templateInputUl: text(draft, "flankingTemplateInputUl"),
        templateClass: text(draft, "flankingTemplateClass"),
        hmwTemplateVerified: text(draft, "longRangeHmwTemplateVerified") === "true",
        qpcrInstrumentProfile: text(draft, "qpcrInstrumentProfile"),
        digitalConsumableId: text(draft, "digitalConsumableId"),
        effectivePartitionVolumeNl: text(draft, "digitalEffectivePartitionVolumeNl"),
        fragmentationEnzyme: text(draft, "digitalFragmentationEnzyme"),
        colonySampleInputUl: text(draft, "colonySampleInputUl"),
        fromRna: text(draft, "fromRna") === "true",
      })
    : undefined;
  const flankingNumericConflicts = flankingNumericPreview?.issues ?? [];
  const contractIssues = requiredContextIssues(moduleId, draft);
  const workflowRequirements = workflowRequirementsFor(moduleId, draft, colonyVectorPrimerRequired);

  const missingRequirements = Array.from(
    new Set([
      ...requiredFields.filter((requirement) => !text(draft, requirement).trim()),
      ...workflowRequirements.filter((requirement) => !text(draft, requirement).trim()),
      ...incompleteTargetPair,
      ...lampScenarioMissing,
      ...flankingNumericConflicts.map((issue) => issue.field),
    ]),
  );

  const digitalPlatformRouteIssue: ValidationIssue[] =
    moduleId === "digital-pcr" &&
    ["thermo-absolute-q", "roche-digital-lightcycler"].includes(text(draft, "digitalPlatformId"))
      ? [
          {
            code: "DIGITAL_PLATFORM_REQUIRES_PROBE_MODULE",
            severity: "error",
            ownerStep: "reaction",
            fieldPath: "digitalPlatformId",
            message:
              "This platform is recognized, but its reviewed chemistry is probe-based. Route this assay to the Pair+Probe digital-PCR module instead of Flanking dye dPCR.",
            source: "flanking-platform-routing",
            blocking: true,
          },
        ]
      : [];

  const readinessIssues: ValidationIssue[] = [
    ...contractIssues,
    ...digitalPlatformRouteIssue,
    ...workflowRequirements
      .filter((field) => !text(draft, field).trim())
      .map((field) => ({
        code: "WORKFLOW_CONTEXT_MISSING",
        severity: "error" as const,
        ownerStep: (moduleId === "restriction-cloning"
          ? "vector"
          : moduleId === "lamp"
            ? "design"
            : "strategy") as ValidationIssue["ownerStep"],
        fieldPath: field,
        message: `Required workflow context is missing: ${field}.`,
        source: "workspace-workflow",
        blocking: true,
      })),
    ...incompleteTargetPair.map((field) => ({
      code: "TARGET_INTERVAL_INCOMPLETE",
      severity: "error" as const,
      ownerStep: "target" as const,
      fieldPath: field,
      message: "Target start and target length must be supplied together.",
      source: "workspace-target",
      blocking: true,
    })),
    ...lampScenarioConflicts.map((issue) => ({
      code: "LAMP_SCENARIO_CONFLICT",
      severity: "error" as const,
      ownerStep: lampScenarioIssueOwner(issue),
      fieldPath: issue.field,
      message: issue.message,
      source: "lamp-contract",
      blocking: true,
    })),
    ...flankingNumericConflicts.map((issue) => ({
      code: "FLANKING_NUMERIC_CONTEXT_INVALID",
      severity: "error" as const,
      ownerStep: "reaction" as const,
      fieldPath: issue.field,
      message: issue.message,
      source: "flanking-contract",
      blocking: true,
    })),
  ];

  const requirementsReady = !readinessIssues.some((issue) => issue.blocking);
  const contextReadyFor = (owner: RequiredContextStep) =>
    !hasBlockingIssue(readinessIssues, owner) &&
    requiredDraftFieldsForStep(moduleId, draft, owner).every((field) => text(draft, field).trim());
  const targetContextReady = contextReadyFor("target") && incompleteTargetPair.length === 0;
  const lampOwnerReady = (owner: "reaction" | "specificity") =>
    !lampScenarioConflicts.some((issue) => lampScenarioIssueOwner(issue) === owner);
  const lampExistingDesignReady =
    moduleId !== "lamp" ||
    text(draft, "assayMode") !== "evaluate" ||
    workflowRequirements.every((requirement) => text(draft, requirement).trim());
  const designContextReady = contextReadyFor("design") && lampExistingDesignReady;
  const strategyContextReady = contextReadyFor("strategy");
  const constraintsContextReady = contextReadyFor("constraints");
  const vectorContextReady = contextReadyFor("vector");
  const reactionContextReady = contextReadyFor("reaction") && lampOwnerReady("reaction");
  const specificityContextReady = contextReadyFor("specificity") && lampOwnerReady("specificity");
  const validationContextReady = contextReadyFor("validation");
  const constructContextReady = contextReadyFor("construct");
  const evaluateExisting = text(draft, "assayMode") === "evaluate";
  const externalPairEvaluator = evaluateExisting && EXISTING_PAIR_EVALUATION_MODULES.has(moduleId);
  const runReady =
    designInputReady &&
    reactionReady &&
    requirementsReady &&
    !externalPairEvaluator &&
    !unsupportedColonyStrategy;
  const cloningVectorReady =
    moduleId !== "restriction-cloning" ||
    [
      "cloningVector",
      "forwardEnzyme",
      "reverseEnzyme",
      "forwardProtectiveSequence",
      "reverseProtectiveSequence",
    ].every((field) => text(draft, field).trim());
  const strategyReady =
    moduleId !== "colony-pcr" ||
    (Boolean(colonyStrategy.trim()) &&
      !unsupportedColonyStrategy &&
      (!colonyVectorPrimerRequired ||
        workflowRequirements.every((field) => text(draft, field).trim())));
  const designStepReady = designContextReady && (!isAssembly || designInputReady);
  const constructReady =
    moduleId === "restriction-cloning"
      ? cloningVectorReady
      : moduleId === "gibson-assembly" || moduleId === "site-directed-mutagenesis"
        ? designInputReady && designContextReady
        : true;

  const done: Record<StepId, boolean> = {
    target: designInputReady && targetContextReady,
    design: designStepReady,
    strategy: strategyReady && strategyContextReady,
    constraints: constraintsContextReady,
    vector: cloningVectorReady && vectorContextReady,
    reaction:
      reactionReady &&
      reactionContextReady &&
      (moduleId !== "lamp" || lampScenarioMissing.length === 0),
    specificity: specificityContextReady,
    validation: validationContextReady,
    construct: constructReady && constructContextReady,
    review: runReady,
  };

  return { bases, segments, missingRequirements, readinessIssues, runReady, done };
}

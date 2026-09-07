"use client";

/**
 * The stepped workspace: a project, filled in one question at a time.
 *
 * Four steps and a result, because a primer design is four separate decisions
 * and putting them on one page makes all four look equally urgent when only
 * the first one is. The tabs are not a wizard — every step is reachable at any
 * time, and the marks on them say what has been answered rather than what is
 * allowed.
 *
 * The draft is saved whenever a step is left. Somebody who pastes a sequence,
 * goes to find their vector map and comes back an hour later should find the
 * sequence still there; losing it is the difference between a tool people
 * return to and one they do not.
 */

import {
  ListChecks,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Dna,
  FlaskConical,
  Hammer,
  Loader2,
  Save,
  TriangleAlert,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";

import { LocalTime } from "@/components/local-time";

import { VectorPrimerPanel } from "@/components/design/bench-tools";
import { CheckPrimers } from "@/components/design/check-primers";
import { CloningTails } from "@/components/design/cloning-tails";
import { EngineFields, asksSomethingExtra } from "@/components/design/engine-fields";
import { KnownVariants } from "@/components/design/known-variants";
import { RunProgress } from "@/components/design/run-progress";
import { planFor, type PagePlan, type StepId, type StepPlan } from "@/components/design/page-plan";
import { ResultView } from "@/components/design/result-view";
import { StaleRunNotice, staleRun } from "@/components/design/stale-run-notice";
import { CopyReportButton } from "@/components/project/copy-report";
import { BenchPanels, Small, Step } from "@/components/project/workspace-parts";
import {
  LampGeometryDiagram,
  SummaryMetric,
  ValidationEvidenceStep,
} from "@/components/project/workspace-evidence";
import { AvoidedRegions, RegionPicker } from "@/components/design/region-picker";
import { SequenceInput } from "@/components/design/sequence-input";
import { approximateBases } from "@/components/design/approximate-bases";
import { FieldGroup, WrappedField } from "@/components/form-parts";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { EXCLUSION_ONLY, NO_REGION } from "@/lib/api/labels";
import { count } from "@/lib/numbers";
import { FLANKING_PROTOCOL_METADATA } from "@/lib/flanking-contract";
import { cn } from "@/lib/utils";
import type {
  EngineId,
  ModuleManifest,
  Preferences,
  Presets,
  Project,
  RunResult,
  RunJob,
  RunSummary,
} from "@/lib/api/types";
import { runNameById } from "@/lib/projects/run-name";
import { engineLabel } from "@/lib/projects/comparison";
import { seededPolymerase, settingsWithinReach } from "@/lib/projects/seed";
import type { RawDraftValues } from "@/lib/projects/draft";
import { placeVectorPrimersAction, rankEnzymesAction } from "@/lib/projects/actions";
import { nucleotideSequenceForCase } from "@/components/design/approximate-bases";
import {
  EXISTING_PAIR_EVALUATION_MODULES,
  workspaceReadiness,
} from "@/components/project/workspace-readiness";
import { useDraftAutosave } from "@/components/project/use-draft-autosave";
import { useWorkspaceRun } from "@/components/project/use-workspace-run";

/** Every field the workspace holds, as the strings a form deals in. */
type Draft = RawDraftValues;

const BLANK: Draft = {
  name: "",
  template: "",
  // Empty until lowercase appears; Scientific-Strict refuses to guess its meaning.
  lowercaseMasking: "",
  targetStart: "",
  targetLength: "",
  avoided: "",
  // Positions the template is known to vary at, as typed. Parsed on the way
  // down rather than here, so a draft round-trip carries what was written.
  variants: "",
  polymerase: "",
  exonJunctions: "",
  purpose: "",
  howMany: "5",
  background: "",
  maxMismatches: "3",
  label: "",
};

/**
 * Constraint fields travel under this prefix.
 *
 * The list of them belongs to the engine and arrives with its presets, so
 * nothing here knows what a flanking pair takes versus what a degenerate one
 * does. A form that hard-codes one engine's fields silently drops the other's.
 */
const CONSTRAINT_PREFIX = "c_";

/*
 * The steps are no longer a constant.
 *
 * Every one of the twenty-one modules rendered this same list in this same
 * order, and a per-assay review found that it fits exactly one of them. LAMP's
 * engine refuses the whole constraints step; Gibson has no target to point at;
 * an assembly has no background genome to be checked against. See
 * `page-plan.ts` for what each assay asks instead.
 */

/** One draft field, always a string. */
function text(draft: Draft, key: string): string {
  return draft[key] ?? "";
}

function readableFieldName(field: string): string {
  return field
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replaceAll("_", " ")
    .toLowerCase();
}

const REQUIREMENT_LABELS: Record<string, string> = {
  background: "exclusion background",
  inclusivity: "target inclusivity panel",
  colonyHostClass: "colony host class",
  colonyPreparation: "colony template preparation",
  colonyProtocolName: "colony PCR SOP / protocol",
  colonyProtocolProvenance: "colony SOP source / revision",
  longRangeProtocol: "named long-range chemistry",
  rpaProtocol: "executable RPA chemistry",
  digitalPartitionFormat: "digital-PCR partition format",
  digitalPlatformId: "digital-PCR platform identity",
  digitalPlatformName: "validated platform / instrument name",
  digitalFragmentationState: "template fragmentation state",
  shares: "nested shared-primer policy",
  margin: "nested inward margin",
  singleTube: "nested tube topology",
  carryoverPrevention: "nested carry-over prevention",
  inverseBranch: "inverse-PCR preparation branch",
  enzyme: "inverse-PCR restriction enzyme",
  leftEndPhosphate: "left-end phosphorylation state",
  rightEndPhosphate: "right-end phosphorylation state",
  circularizationProvenance: "circularisation provenance",
  linearControlProvenance: "linear-control provenance",
  methylationBranch: "methylation branch",
  probeProtocol: "probe chemistry authority",
  tetraMinBandSeparationBp: "validated band-resolution threshold",
  kaspAssayMode: "KASP assay mode",
  kaspPlateFormat: "KASP plate format",
  kaspInstrumentModel: "KASP instrument model",
  kaspRoxPolicy: "KASP ROX policy",
  alignmentMode: "universal-primer alignment authority",
  tilingOperation: "tiling lifecycle operation",
  tilingAlignmentMode: "tiling alignment authority",
  overlap: "tiling overlap",
  pools: "tiling pool count",
  panelMode: "tiling panel mode",
  existingBed: "existing scheme BED",
  schemeConfig: "existing scheme configuration",
  primerName: "scheme primer identity",
  raceDirection: "RACE direction",
  raceAdapter: "RACE partner / adapter",
  racePartnerSequence: "custom RACE partner sequence",
  raceSubstrate: "RACE substrate",
  racePreparation: "RACE preparation",
  raceRound: "RACE amplification round",
  direction: "sequencing read direction",
  deadZone: "sequencing dead zone",
  readLength: "usable sequencing read length",
  sequencingInstrumentName: "sequencing instrument name",
  assemblyProtocol: "Gibson assembly protocol",
  circular: "construct / template topology",
  tailProtocol: "restriction-tail protocol",
  forwardEnzyme: "forward restriction enzyme",
  reverseEnzyme: "reverse restriction enzyme",
  forwardProtectiveSequence: "forward protective bases",
  reverseProtectiveSequence: "reverse protective bases",
  postAmplificationProtocol: "mutagenesis recovery protocol",
  editKind: "edit kind",
  editAt: "edit coordinate",
  editTo: "inserted / replacement sequence",
  editReplacing: "sequence being replaced / deleted",
  targetStart: "target-region start",
  targetLength: "target-region length",
};

const NAMED_PROTOCOL_FIELDS: Record<string, { field: string; label: string }> = {
  "standard-pcr": { field: "standardPcrProtocol", label: "Bench chemistry" },
  "long-range-pcr": { field: "longRangeProtocol", label: "Long-range protocol" },
  "qpcr-sybr": { field: "qpcrProtocol", label: "Dye-qPCR chemistry" },
  rpa: { field: "rpaProtocol", label: "RPA chemistry" },
  "digital-pcr": { field: "digitalProtocol", label: "Digital-PCR chemistry" },
  lamp: { field: "lampProtocol", label: "LAMP protocol" },
};

function humanChoice(field: string, value: string): string {
  const protocolMeta = FLANKING_PROTOCOL_METADATA[value];
  if (protocolMeta) return protocolMeta.label;
  const labels: Record<string, string> = {
    "not-selected": "Not selected",
    "neb-taq-m0273": "NEB Taq DNA Polymerase M0273",
    "neb-q5-hot-start-m0493": "NEB Q5 Hot Start High-Fidelity M0493",
    "neb-q5u-hot-start-m0515": "NEB Q5U Hot Start High-Fidelity M0515",
    "thermo-dreamtaq-hot-start-ep170x": "Thermo DreamTaq Hot Start EP1701–EP1704",
    "thermo-phusion-plus": "Thermo Phusion Plus DNA Polymerase",
    "promega-gotaq-m300": "Promega GoTaq DNA Polymerase M300",
    "thermo-platinum-superfi-ii": "Thermo Fisher Platinum SuperFi II PCR Master Mix",
    "neb-longamp-taq-m0323": "NEB LongAmp Taq M0323",
    "neb-q5-xt-m2499": "NEB Q5-XT Hot Start High-Fidelity M2499",
    "promega-gotaq-long-m4021": "Promega GoTaq Long PCR Master Mix M4021",
    "thermo-platinum-superfi-ii-longrange": "Thermo Fisher Platinum SuperFi II · long-range branch",
    "takara-primestar-gxl-r050a-standard": "Takara PrimeSTAR GXL R050A · Standard",
    "qiagen-ultrarun-longrange-206442-206444": "QIAGEN UltraRun LongRange 206442/206444",
    "thermo-long-pcr-k018x": "Thermo Long PCR Enzyme Mix K0181/K0182 · historical",
    "bio-rad-itaq-sybr": "Bio-Rad iTaq Universal SYBR Green",
    "neb-luna-universal-m3003": "NEB Luna Universal qPCR M3003",
    "neb-luna-one-step-rt-qpcr-e3005": "NEB Luna One-Step RT-qPCR E3005",
    "thermo-powerup-sybr-a2574x": "Thermo Fisher PowerUp SYBR Green",
    "promega-gotaq-qpcr-a600x": "Promega GoTaq qPCR Master Mix A6001/A6002",
    "promega-gotaq-one-step-rt-qpcr-a6020": "Promega GoTaq 1-Step RT-qPCR A6020",
    "twistamp-basic": "TwistAmp Basic",
    "twistamp-liquid-basic": "TwistAmp Liquid Basic",
    "thermo-lyo-ready-rpa": "Thermo Fisher Lyo-ready RPA / RT-RPA",
    "bio-rad-qx200-evagreen": "Bio-Rad QX200 ddPCR EvaGreen",
    "bio-rad-qx700-naica-evagreen": "Bio-Rad naica ddPCR Mix / EvaGreen · QX700/Nio/naica",
    "bio-rad-qx700-evagreen-supermix": "Bio-Rad QX700 ddPCR EvaGreen Supermix 5X",
    "qiagen-qiacuity-eg": "QIAGEN QIAcuity EG PCR Kit",
    "qiagen-qiacuity-onestep-advanced-eg": "QIAGEN QIAcuity OneStep Advanced EvaGreen",
    "not-specified": "Not specified yet",
    fluorescence: "Fluorescence",
    colorimetric: "Colorimetric",
    turbidity: "Turbidity",
    "other-validated": "Other validated",
    droplet: "Droplet",
    chip: "Chip",
    chamber: "Chamber",
    "not-assessed": "Not assessed yet",
    "not-required": "Not required by current SOP",
    planned: "Planned",
    performed: "Performed",
    bacterial: "Bacterial",
    yeast: "Yeast",
    "filamentous-fungus": "Filamentous fungus",
    microalgae: "Microalgae",
    "direct-transfer": "Direct colony transfer",
    "water-lysate": "Water lysate",
    "buffer-lysate": "Buffer / TE lysate",
    "host-specific-lysis": "Host-specific lysis",
    "primerexplorer-v5-compat": "PrimerExplorer V5 public-rule profile",
    "pcrstudio-evidence-2026": "PCRStudio Evidence 2026",
    none: "No synthetic linker",
    tttt: "TTTT linker",
  };
  if (field === "lampProtocol" && !value) return "Not selected";
  return labels[value] ?? (value || "Not selected");
}

export function Workspace({
  project,
  presets,
  runs,
  latest,
  showing,
  engine,
  runnable,
  canFetch,
  canAlign,
  preferences,
  assayDefaults,
  modifiers,
  requirements,
}: {
  project: Project;
  presets: Presets;
  runs: RunSummary[];
  /** Which search runs, so the form can ask what this engine needs. */
  engine: EngineId;
  /** The saved result being shown: the one asked for, or the most recent. */
  latest: RunResult | null;
  /** Which run that is, so the page can say so rather than implying the last. */
  showing: string | null;
  /** Whether the engine behind this module computes yet. */
  runnable: boolean;
  /** Whether an accession can be looked up in this build. */
  canFetch: boolean;
  /** Whether an aligner is installed on the server. */
  canAlign: boolean;
  /** What this person has told us about how they work. */
  preferences: Preferences;
  /** What this assay differs from its engine's defaults by. */
  assayDefaults: ModuleManifest["defaults"];
  /** What this assay may be combined with, from its own profile. */
  modifiers: string[];
  /** Inputs the assay cannot be run without, from its own profile. */
  requirements: string[];
}) {
  /*
   * What this assay's page asks, in what order, in its own words.
   *
   * Read once from the module id rather than assumed: two assays on the same
   * engine can want different pages, and eight of them share flanking-pair.
   */
  const plan = useMemo(() => planFor(project.moduleId), [project.moduleId]);
  const [step, setStep] = useState<StepId>(() => plan.steps[0]!.id);

  const [draft, setDraft] = useState<Draft>(() => ({
    ...BLANK,
    // A visible substrate selector must be real request provenance. Do not
    // seed this on assays that never ask the RNA/DNA question.
    ...(modifiers.includes("reverse-transcription") ? { fromRna: "false" } : {}),
    // Editable UI starting states come from the assay page itself. They are
    // seeded before saved settings so a returning project keeps what the user
    // actually chose, unlike canonical `fixed` identity below.
    ...plan.initial,
    /*
     * The enzyme somebody keeps on their bench, when this assay offers it.
     *
     * Only when it offers it. This guard was written before it could fire —
     * every module offered every enzyme then — against the day an assay
     * narrowed its list. That day came: LAMP offers one enzyme now, and a
     * stored preference for Taq would otherwise have walked straight past it.
     *
     * And only as a starting point. It seeds a new draft; a project that has
     * already been set up keeps what was set up, because `project.settings`
     * spreads over the top.
     */
    polymerase: seededPolymerase(presets, preferences, assayDefaults).id ?? "",
    purpose:
      (assayDefaults.defaultPurpose &&
      presets.purposes.some((entry) => entry.id === assayDefaults.defaultPurpose)
        ? assayDefaults.defaultPurpose
        : assayDefaults.purposes.length === 1
          ? assayDefaults.purposes[0]
          : "") ?? "",
    ...settingsWithinReach(project.settings as Draft, presets, preferences, assayDefaults),
    // Canonical assay identity wins *after* restoring a saved draft. A project
    // can outlive the module/profile that created it; fixed geometry/protocol
    // fields must never be overridden by stale saved state from another assay.
    ...plan.fixed,
  }));
  const { saved, save } = useDraftAutosave({ project, draft, setDraft, blank: BLANK });
  const {
    state,
    job,
    activeJob,
    startingRun,
    pending,
    cancellingRun,
    submit,
    cancelCurrentRun,
    result,
    resultRef,
    announcement,
  } = useWorkspaceRun({ projectId: project.id, latest });

  const set = useCallback((key: string, value: string) => {
    setDraft((previous) => ({ ...previous, [key]: value }));
  }, []);

  const go = useCallback(
    (next: StepId) => {
      void save();
      setStep(next);
    },
    [save],
  );

  const previousStep = useRef(step);
  useEffect(() => {
    if (previousStep.current === step) return;
    previousStep.current = step;
    requestAnimationFrame(() => {
      document.getElementById("workspace-step-heading")?.focus({ preventScroll: false });
    });
  }, [step]);

  const { bases, segments, missingRequirements, runReady, done } = workspaceReadiness({
    draft,
    engine,
    moduleId: project.moduleId,
    requirements,
  });

  // The words for whichever step is showing. Undefined would mean a step body
  // rendered for an assay whose plan does not include it, which cannot happen —
  // but the fallback keeps a headline rather than an empty heading if it did.
  const words = plan.steps.find((entry) => entry.id === step) ?? plan.steps[0]!;

  const index = plan.steps.findIndex((entry) => entry.id === step);
  const previous = index > 0 ? plan.steps[index - 1] : null;
  const next = index >= 0 && index < plan.steps.length - 1 ? plan.steps[index + 1] : null;

  // The saved run on screen, when the result shown is one of them. A design
  // that has just run is not in this list yet, and a report naming somebody
  // else's run would be worse than no button — so the export waits until the
  // run is actually saved and listed.
  const shownRun =
    !state.run && result ? (runs.find((run) => run.id === showing) ?? runs[0] ?? null) : null;

  return (
    <div className="space-y-5">
      {/* Labels stay visible at every width; the row scrolls horizontally on
          narrow screens so a numbered step never becomes an anonymous icon. */}
      <nav
        aria-label="Design steps"
        className="workbench-card overflow-hidden rounded-xl border bg-surface-wash/45 p-1.5"
      >
        <ol className="flex max-w-full min-w-0 gap-1 overflow-auto">
          {plan.steps.map((entry, position) => {
            const active = entry.id === step;
            const Icon = entry.icon;
            return (
              <li key={entry.id}>
                <button
                  type="button"
                  onClick={() => go(entry.id)}
                  aria-current={active ? "step" : undefined}
                  aria-label={`${entry.title}, ${done[entry.id] ? "answered" : "not yet answered"}`}
                  className={cn(
                    "flex min-h-10 min-w-max items-center justify-start gap-2 rounded-lg border border-transparent px-2.5 py-2 text-sm whitespace-nowrap transition-all focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none sm:min-h-0 sm:px-3",
                    active
                      ? "border-primary/20 bg-primary/10 font-medium text-primary shadow-xs"
                      : "text-muted-foreground hover:bg-surface-warm/45 hover:text-foreground",
                  )}
                >
                  <span
                    aria-hidden="true"
                    className={cn(
                      "flex size-5 shrink-0 items-center justify-center rounded-full border text-xs tabular-nums",
                      done[entry.id]
                        ? "border-success text-success"
                        : "border-muted-foreground/40 text-muted-foreground",
                    )}
                  >
                    {done[entry.id] ? <Check className="size-3" /> : position + 1}
                  </span>
                  <Icon className="hidden size-4 sm:block" aria-hidden="true" />
                  <span>{entry.title}</span>
                </button>
              </li>
            );
          })}
        </ol>
      </nav>

      {/* Main Workspace Layout: 2 Columns for Steps 1-4 on Desktop, Full Width for Review & Results */}
      <div
        className={cn(
          step !== "review" && !result ? "grid items-start gap-6 lg:grid-cols-12" : "space-y-4",
        )}
      >
        <div className={cn(step !== "review" && !result ? "space-y-4 lg:col-span-8" : "space-y-4")}>
          <form
            action={submit}
            onSubmit={step === "review" ? undefined : (event) => event.preventDefault()}
            className="space-y-4"
          >
            <input type="hidden" name="projectId" value={project.id} />
            <input type="hidden" name="moduleId" value={project.moduleId} />
            <input type="hidden" name="engine" value={engine} />
            {Object.entries(draft).map(([key, value]) => (
              <input key={key} type="hidden" name={key} value={value} />
            ))}

            {step === "target" ? (
              <TargetStep
                draft={draft}
                set={set}
                bases={bases}
                engine={engine}
                moduleId={project.moduleId}
                canFetch={canFetch}
                canAlign={canAlign}
                plan={plan}
                words={words}
                modifiers={modifiers}
              />
            ) : step === "design" ? (
              <AssayDesignStep
                draft={draft}
                set={set}
                presets={presets}
                words={words}
                engine={engine}
                moduleId={project.moduleId}
              />
            ) : step === "strategy" ? (
              <StrategyStep
                draft={draft}
                set={set}
                words={words}
                moduleId={project.moduleId}
                engine={engine}
              />
            ) : step === "constraints" ? (
              <ConstraintsStep
                draft={draft}
                set={set}
                presets={presets}
                words={words}
                moduleId={project.moduleId}
              />
            ) : step === "vector" ? (
              <VectorStep
                draft={draft}
                set={set}
                words={words}
                canFetch={canFetch}
                template={text(draft, "template")}
              />
            ) : step === "reaction" ? (
              <ReactionStep
                draft={draft}
                set={set}
                presets={presets}
                seeded={seededPolymerase(presets, preferences, assayDefaults)}
                words={words}
                engine={engine}
                moduleId={project.moduleId}
              />
            ) : step === "specificity" ? (
              <SpecificityStep
                draft={draft}
                set={set}
                canFetch={canFetch}
                words={words}
                engine={engine}
                moduleId={project.moduleId}
              />
            ) : step === "validation" ? (
              <ValidationEvidenceStep
                draft={draft}
                set={set}
                words={words}
                moduleId={project.moduleId}
              />
            ) : step === "construct" ? (
              <ConstructStep
                draft={draft}
                set={set}
                words={words}
                template={text(draft, "template")}
                moduleId={project.moduleId}
              />
            ) : (
              <ReviewStep
                draft={draft}
                set={set}
                presets={presets}
                bases={bases}
                engine={engine}
                segments={segments}
                pending={pending}
                job={job}
                activeJob={activeJob}
                startingRun={startingRun}
                cancellingRun={cancellingRun}
                cancelCurrentRun={cancelCurrentRun}
                runnable={runnable}
                ready={runReady}
                missingRequirements={missingRequirements}
                plan={plan}
                words={words}
                moduleId={project.moduleId}
              />
            )}

            <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-3">
              <div className="flex items-center gap-2">
                {previous ? (
                  <Button type="button" variant="outline" size="sm" onClick={() => go(previous.id)}>
                    <ChevronLeft className="size-3.5" />
                    {previous.title}
                  </Button>
                ) : null}
                {next ? (
                  <Button type="button" variant="outline" size="sm" onClick={() => go(next.id)}>
                    {next.title}
                    <ChevronRight className="size-3.5" />
                  </Button>
                ) : null}
              </div>

              <div className="flex items-center gap-3 text-xs text-muted-foreground">
                {saved === "saving" ? (
                  <span className="flex items-center gap-1.5">
                    <Loader2 className="size-3 animate-spin" />
                    Saving
                  </span>
                ) : saved === "saved" ? (
                  <span className="flex items-center gap-1.5 text-success">
                    <Save className="size-3" />
                    Draft saved
                  </span>
                ) : saved === "error" ? (
                  // Stays until the next save attempt: clearing it on a timer
                  // would let the one moment it matters scroll past unread.
                  <span role="status" className="flex items-center gap-1.5 text-destructive">
                    <TriangleAlert className="size-3" />
                    Draft not saved
                  </span>
                ) : null}
                {step !== "review" ? (
                  <Button
                    type="button"
                    size="sm"
                    onClick={() => go("review")}
                    disabled={!done.target}
                  >
                    <ListChecks className="size-3.5" />
                    Review and run
                  </Button>
                ) : null}
              </div>
            </div>
          </form>

          {state.error ? (
            <div
              role="alert"
              className="rounded-lg border border-destructive/40 bg-destructive/5 p-3.5 text-sm text-destructive"
            >
              {state.error}
            </div>
          ) : null}
        </div>

        {/* Sidebar Live Parameter Inspector on Steps 1-4 */}
        {step !== "review" && !result ? (
          <div className="lg:sticky lg:top-4 lg:col-span-4">
            <WorkspaceSidebar
              projectId={project.id}
              draft={draft}
              bases={bases}
              presets={presets}
              engine={engine}
              plan={plan}
              done={done}
              step={step}
              onGo={go}
              runs={runs}
              showing={showing}
            />
          </div>
        ) : null}
      </div>

      <p key={state.run?.id ?? "idle"} role="status" aria-live="polite" className="sr-only">
        {announcement}
      </p>

      {result ? (
        <div
          ref={resultRef}
          tabIndex={-1}
          className="workbench-result space-y-2.5 rounded-2xl border-t border-primary/20 pt-5 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          {!state.run && latest ? (
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-muted-foreground">
                {showing && showing !== runs[0]?.id
                  ? `Showing “${runNameById(runs, showing)}” from the history below.`
                  : `Showing the most recent saved run — “${runNameById(runs, runs[0]?.id ?? null)}”. Run again to replace it.`}
              </p>
              {shownRun ? (
                <CopyReportButton
                  label={runNameById(runs, shownRun.id)}
                  createdAt={shownRun.createdAt}
                  moduleName={engineLabel(result)}
                  result={result!}
                />
              ) : null}
            </div>
          ) : null}
          {staleRun(result) ? <StaleRunNotice /> : null}

          <ResultView result={result} />
        </div>
      ) : null}
    </div>
  );
}

function WorkspaceSidebar({
  projectId,
  draft,
  bases,
  presets,
  engine,
  plan,
  done,
  step,
  onGo,
  runs,
  showing,
}: {
  projectId: string;
  draft: Draft;
  bases: number;
  presets: Presets;
  engine: EngineId;
  plan: PagePlan;
  done: Record<StepId, boolean>;
  step: StepId;
  onGo: (step: StepId) => void;
  runs: RunSummary[];
  showing: string | null;
}) {
  const polymeraseId = text(draft, "polymerase");
  const polymerase = presets.polymerases.find((p) => p.id === polymeraseId);
  const targetStart = text(draft, "targetStart");
  const targetLength = text(draft, "targetLength");
  const isCircular = text(draft, "circular") === "true";
  const fromRna = text(draft, "fromRna") === "true";
  const isAssembly = engine === "junction-primers";

  const template = text(draft, "template");
  const gcPercent = useMemo(() => {
    if (!template) return null;
    const clean = template
      .replace(/^>.*$/gm, "")
      .replace(/[^A-Za-z]/g, "")
      .toUpperCase();
    if (!clean.length) return null;
    let gc = 0;
    for (let i = 0; i < clean.length; i++) {
      if (clean[i] === "G" || clean[i] === "C" || clean[i] === "S") gc++;
    }
    return ((gc / clean.length) * 100).toFixed(1);
  }, [template]);

  return (
    <aside className="space-y-4">
      {/* Target & Chemistry Summary Card */}
      <Card className="workbench-card">
        <CardHeader className="border-b bg-surface-wash/30 pb-2">
          <div className="flex items-center gap-2 text-primary">
            <Dna className="size-4" />
            <CardTitle className="font-serif text-sm font-semibold tracking-tight text-foreground">
              Assay Parameters
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-2 pt-3 text-xs">
          <div className="flex items-center justify-between border-b border-border/50 py-1">
            <span className="text-muted-foreground">Target Length</span>
            <span className="font-medium text-foreground tabular-nums">
              {bases > 0 ? `${count(bases)} bp` : "—"}
            </span>
          </div>

          {gcPercent ? (
            <div className="flex items-center justify-between border-b border-border/50 py-1">
              <span className="text-muted-foreground">Estimated GC%</span>
              <span className="font-medium text-foreground tabular-nums">{gcPercent}%</span>
            </div>
          ) : null}

          <div className="flex items-center justify-between border-b border-border/50 py-1">
            <span className="text-muted-foreground">Template Type</span>
            <span className="font-medium text-foreground">
              {isAssembly
                ? "Fragment assembly"
                : fromRna
                  ? "RNA (reverse-transcription workflow)"
                  : isCircular
                    ? "Circular DNA"
                    : "Linear DNA"}
            </span>
          </div>

          {targetStart && targetLength ? (
            <div className="flex items-center justify-between border-b border-border/50 py-1">
              <span className="text-muted-foreground">Target Span</span>
              <span className="font-medium text-foreground tabular-nums">
                {targetStart} – {Number(targetStart) + Number(targetLength) - 1} bp
              </span>
            </div>
          ) : targetStart || targetLength ? (
            <div className="flex items-center justify-between border-b border-border/50 py-1">
              <span className="text-muted-foreground">Target Span</span>
              <span className="font-medium text-warning">
                incomplete — start and length travel together
              </span>
            </div>
          ) : null}

          <div className="flex items-center justify-between py-1">
            <span className="text-muted-foreground">
              {isAssembly ? "Joining chemistry" : "Polymerase context"}
            </span>
            <span
              className="max-w-[140px] truncate font-medium text-foreground"
              title={
                isAssembly
                  ? text(draft, "method") || "Not chosen"
                  : (polymerase?.name ?? "Not chosen")
              }
            >
              {isAssembly
                ? text(draft, "method") || "Not chosen"
                : (polymerase?.name ?? "Not chosen")}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Quick Step Checklist & Direct Jump */}
      <Card className="workbench-card">
        <CardHeader className="border-b bg-surface-wash/30 pb-2">
          <div className="flex items-center gap-2 text-primary">
            <CheckCircle2 className="size-4" />
            <CardTitle className="font-serif text-sm font-semibold tracking-tight text-foreground">
              Design Workflow
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-2 pt-3">
          <ul className="space-y-1 text-xs">
            {plan.steps.map((entry, index) => (
              <StepJumpButton
                key={entry.id}
                label={`${index + 1}. ${entry.title}`}
                active={step === entry.id}
                done={done[entry.id]}
                onClick={() => onGo(entry.id)}
              />
            ))}
          </ul>

          <div className="border-t pt-2">
            <Button
              type="button"
              className="w-full gap-1.5 shadow-xs"
              size="sm"
              disabled={!done.target}
              onClick={() => onGo("review")}
            >
              <FlaskConical className="size-3.5" />
              <span>Review & Run</span>
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Previous Runs History */}
      {runs.length > 0 ? (
        <Card className="workbench-card">
          <CardHeader className="border-b bg-surface-wash/30 pb-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-muted-foreground">
                <Clock className="size-4" />
                <CardTitle className="font-serif text-sm font-semibold tracking-tight text-foreground">
                  Run History ({runs.length})
                </CardTitle>
              </div>
            </div>
          </CardHeader>
          <CardContent className="max-h-48 space-y-1 overflow-y-auto pt-2 text-xs">
            {runs.map((r) => (
              <Link
                key={r.id}
                href={`/projects/${projectId}?run=${r.id}`}
                className={cn(
                  "flex w-full items-center justify-between rounded-lg p-2 text-left transition-colors",
                  showing === r.id
                    ? "bg-primary/10 font-medium text-primary"
                    : "text-muted-foreground hover:bg-surface-warm/35 hover:text-foreground",
                )}
              >
                <span className="truncate">{runNameById(runs, r.id)}</span>
                <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
                  <LocalTime iso={r.createdAt} relative />
                </span>
              </Link>
            ))}
          </CardContent>
        </Card>
      ) : null}
    </aside>
  );
}

function StepJumpButton({
  label,
  active,
  done,
  onClick,
}: {
  label: string;
  active: boolean;
  done: boolean;
  onClick: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        className={cn(
          "flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-left transition-all focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
          active
            ? "bg-primary/10 font-medium text-primary"
            : "text-muted-foreground hover:bg-surface-warm/35 hover:text-foreground",
        )}
      >
        <span>{label}</span>
        {done ? (
          <Check className="size-3.5 text-success" />
        ) : (
          <span className="size-1.5 rounded-full bg-muted-foreground/40" />
        )}
      </button>
    </li>
  );
}

/* ── The steps ─────────────────────────────────────────────────────────── */

function TargetStep({
  draft,
  set,
  bases,
  engine,
  moduleId,
  canFetch,
  canAlign,
  plan,
  words,
  modifiers,
}: {
  draft: Draft;
  set: (key: string, value: string) => void;
  bases: number;
  /** Two engines ask for things the others do not, and neither is defaultable. */
  engine: EngineId;
  moduleId: string;
  canFetch: boolean;
  canAlign: boolean;
  plan: PagePlan;
  words: StepPlan;
  /** What this assay may be combined with, from its own profile. */
  modifiers: string[];
}) {
  const canEvaluateExisting =
    engine === "flanking-pair" && EXISTING_PAIR_EVALUATION_MODULES.has(moduleId);
  const canValidateLamp = engine === "loop-set" && moduleId === "lamp";
  const evaluateExisting =
    (canEvaluateExisting || canValidateLamp) && text(draft, "assayMode") === "evaluate";

  return (
    <Step title={words.heading} description={words.description}>
      {canEvaluateExisting || canValidateLamp ? (
        <FieldGroup
          label="Workflow"
          className="rounded-lg border border-border/60 bg-surface-wash/25 p-3"
        >
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant={!evaluateExisting ? "default" : "outline"}
              aria-pressed={!evaluateExisting}
              onClick={() => set("assayMode", "design")}
            >
              {canValidateLamp ? "Design new set" : "Design new primers"}
            </Button>
            <Button
              type="button"
              size="sm"
              variant={evaluateExisting ? "default" : "outline"}
              aria-pressed={evaluateExisting}
              onClick={() => set("assayMode", "evaluate")}
            >
              {canValidateLamp ? "Validate an existing set" : "Evaluate an existing pair"}
            </Button>
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground">
            {canValidateLamp
              ? "Validation maps F3/B3/FIP/BIP and optional LF/LB to one target locus, checks LAMP geometry, thermodynamics, interactions, inclusivity and specificity without redesigning the set."
              : "Evaluation uses this module's canonical assay profile and reports measurements and specificity evidence without redesigning or ranking the pair. It does not convert in-silico checks into experimental validation."}
          </p>
        </FieldGroup>
      ) : null}
      <SequenceInput
        label="Sequence"
        value={text(draft, "template")}
        onChange={(next) => set("template", next)}
        canFetch={canFetch}
        canAlign={canAlign}
        placeholder=">my_target&#10;ATGCGTACGATCGATCGTAGCTAGCTAGCATCGATCGATCG…"
        hint="FASTA, GenBank, or bare bases. Several records are allowed — you will be asked what to do with them."
      />

      {/[acgturyswkmbdhvn]/.test(nucleotideSequenceForCase(text(draft, "template"))) ? (
        <FieldGroup
          label="Meaning of lowercase bases"
          hint="Required because case cannot safely be inferred. Primer3 can interpret lowercase as soft masking, but PCRStudio will not decide that from the fraction of lowercase sequence."
        >
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant={text(draft, "lowercaseMasking") === "true" ? "default" : "outline"}
              size="sm"
              onClick={() => set("lowercaseMasking", "true")}
            >
              Lowercase is intentional soft masking
            </Button>
            <Button
              type="button"
              variant={text(draft, "lowercaseMasking") === "false" ? "default" : "outline"}
              size="sm"
              onClick={() => set("lowercaseMasking", "false")}
            >
              Lowercase is formatting only
            </Button>
          </div>
        </FieldGroup>
      ) : null}

      {canEvaluateExisting && evaluateExisting ? (
        <CheckPrimers
          template={text(draft, "template")}
          moduleId={moduleId}
          lowercaseMasking={
            text(draft, "lowercaseMasking") === "true"
              ? true
              : text(draft, "lowercaseMasking") === "false"
                ? false
                : undefined
          }
        />
      ) : (
        <>
          {/*
           * Asked only where the oligos go on to something else.
           *
           * A tiled scheme is pooled and sequenced and a degenerate pair is read
           * off a universal primer, so in both cases every oligo carries something
           * fixed by what happens after the PCR. There is no catalogue behind this
           * on purpose: which adapter belongs here is decided by the sequencer
           * somebody has, not by anything derivable from a template.
           */}
          {plan.asks?.includes("tails") ? (
            <div className="space-y-3">
              <WrappedField
                label="5′ tail on every forward oligo"
                hint="Left empty, nothing is added. What you type goes in front of the sequence you order; the melting temperatures stay the annealing halves', which is what the first round actually does."
              >
                <Input
                  value={text(draft, "tailForward")}
                  onChange={(event) => set("tailForward", event.target.value)}
                  placeholder="TCGTCGGCAGCGTCAGATGTGTATAAGAGACAG"
                  className="font-mono text-xs sm:max-w-lg"
                />
              </WrappedField>
              <WrappedField label="5′ tail on every reverse oligo" hint="Usually a different one.">
                <Input
                  value={text(draft, "tailReverse")}
                  onChange={(event) => set("tailReverse", event.target.value)}
                  placeholder="GTCTCGTGGGCTCGGAGATGTGTATAAGAGACAG"
                  className="font-mono text-xs sm:max-w-lg"
                />
              </WrappedField>
            </div>
          ) : null}

          {/*
           * Asked only where a plasmid is an ordinary template for this assay.
           *
           * The pair engine is shared by eight modules and the question is real
           * for a colony screen and meaningless for an RPA assay on genomic DNA,
           * so it comes from the assay's own plan rather than from what the engine
           * happens to accept. What it changes is not cosmetic: a primer sitting
           * across the join is invisible to a scan of the string somebody pasted,
           * and which primers those are depends on where the file begins.
           */}
          {plan.asks?.includes("circular") ? (
            <WrappedField
              label="Is this a circle?"
              hint="A plasmid has no ends, but the sequence you pasted does. Saying so lets the specificity scan look across the join."
            >
              <select
                value={text(draft, "circular") || "false"}
                onChange={(event) => set("circular", event.target.value)}
                className="h-9 w-full rounded-lg border border-border/70 bg-surface-wash/35 px-3 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none sm:max-w-sm"
              >
                <option value="false">Linear — a PCR product, a gene, a chromosome</option>
                <option value="true">Circular — a plasmid or a circular genome</option>
              </select>
            </WrappedField>
          ) : null}

          {/*
           * Asked only where the assay says it can be.
           *
           * Eight profiles declare the reverse-transcription modifier and not one
           * of them could say so, which made the modifier a label rather than a
           * setting. It is not cosmetic: a one-step RT-PCR whose programme has no
           * RT hold amplifies nothing, and the hold has to come before the first
           * denaturation rather than after it.
           */}
          {modifiers.includes("reverse-transcription") ? (
            <WrappedField
              label="What is in the tube to start with?"
              hint="An RT step goes in front of the programme, and its numbers belong to whichever RT enzyme you use rather than to the polymerase."
            >
              <select
                value={text(draft, "fromRna") || "false"}
                onChange={(event) => {
                  set("fromRna", event.target.value);
                  if (event.target.value !== "true") set("exonJunctions", "");
                }}
                className="h-9 w-full rounded-lg border border-border/70 bg-surface-wash/35 px-3 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none sm:max-w-sm"
              >
                <option value="false">DNA — genomic, plasmid, or a PCR product</option>
                <option value="true">RNA — this is a reverse-transcription reaction</option>
              </select>
            </WrappedField>
          ) : null}

          {engine === "flanking-pair" && text(draft, "fromRna") === "true" ? (
            <WrappedField
              label="Transcript exon junctions (optional)"
              hint="Enter the upstream exon base numbers, for example 450 means the boundary between bases 450 and 451. Every reported pair will have at least one primer crossing a supplied boundary."
            >
              <Input
                value={text(draft, "exonJunctions")}
                onChange={(event) => set("exonJunctions", event.target.value)}
                placeholder="450, 812"
                inputMode="numeric"
                className="font-mono text-xs sm:max-w-sm"
              />
            </WrappedField>
          ) : null}

          {/*
           * Asked only where the assay says it can be, the same as the RT control
           * above and for the same reason. `variant-masking` was declared on five
           * profiles and read by nothing; gating on the registry rather than on a
           * list kept here means the control appears exactly where the modifier
           * says it applies, and cannot drift from it.
           */}
          {modifiers.includes("variant-masking") ? (
            <KnownVariants
              value={text(draft, "variants")}
              onChange={(next) => set("variants", next)}
              length={bases}
            />
          ) : null}

          <WrappedField label="Call it" hint="Used to name the oligos you order.">
            <Input
              value={text(draft, "name")}
              onChange={(event) => set("name", event.target.value)}
              placeholder="from the FASTA header"
              className="sm:max-w-sm"
            />
          </WrappedField>

          <div className="border-t pt-4">
            {/*
             * Only the tools this assay uses.
             *
             * These rendered on all twenty-one pages: the RPA page carried the
             * restriction-enzyme chooser under a heading explaining what an inverse
             * PCR needs, which is neither true of RPA nor answerable from it.
             */}
            {plan.tools.length > 0 ? (
              <BenchPanels
                template={text(draft, "template")}
                only={plan.tools}
                draft={draft}
                set={set}
              />
            ) : null}

            {asksSomethingExtra(engine, moduleId) ? (
              <EngineFields
                engine={engine}
                moduleId={moduleId}
                section="target"
                value={(key) => text(draft, key)}
                onChange={(key, next) => set(key, next)}
              />
            ) : null}

            {/* Several engines have no region to point at, so offering one would be
            offering a control whose value is thrown away. Each is told what it
            needs by its own fields above. */}
            {/* No region to point at, but somewhere a primer must not go. */}
            {EXCLUSION_ONLY.includes(engine) ? (
              <AvoidedRegions
                value={text(draft, "avoided")}
                onChange={(next) => set("avoided", next)}
                length={bases}
              />
            ) : null}

            {NO_REGION.includes(engine) || moduleId === "restriction-cloning" ? null : (
              <RegionPicker
                length={bases}
                start={text(draft, "targetStart")}
                span={text(draft, "targetLength")}
                avoided={text(draft, "avoided")}
                onChange={(next) => {
                  set("targetStart", next.start);
                  set("targetLength", next.span);
                }}
                onAvoidedChange={(next) => set("avoided", next)}
                mode={
                  moduleId === "race"
                    ? "race-gsp"
                    : moduleId === "sequencing-primer"
                      ? "sequencing-target"
                      : "product"
                }
              />
            )}
          </div>
        </>
      )}
    </Step>
  );
}

function AssayDesignStep({
  draft,
  set,
  presets,
  words,
  engine,
  moduleId,
}: {
  draft: Draft;
  set: (key: string, value: string) => void;
  presets: Presets;
  words: StepPlan;
  engine: EngineId;
  moduleId: string;
}) {
  if (moduleId === "restriction-cloning") {
    return (
      <ConstraintsStep
        draft={draft}
        set={set}
        presets={presets}
        words={words}
        moduleId={moduleId}
      />
    );
  }

  const validatingLamp = moduleId === "lamp" && text(draft, "assayMode") === "evaluate";
  return (
    <Step title={words.heading} description={words.description}>
      {moduleId === "lamp" ? <LampGeometryDiagram /> : null}
      {validatingLamp ? (
        <div className="space-y-4 rounded-lg border border-border/60 bg-surface-wash/20 p-3">
          <div>
            <p className="text-sm font-medium">Existing LAMP set</p>
            <p className="text-xs leading-relaxed text-muted-foreground">
              Enter supplier-ready 5′→3′ oligos. FIP/BIP split lengths identify the target-derived
              F1c/B1c 5′ segments; PCRStudio will not guess that seam from the midpoint.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {(
              [
                ["existingLampF3", "F3"],
                ["existingLampB3", "B3"],
                ["existingLampFip", "FIP (F1c + linker + F2)"],
                ["existingLampBip", "BIP (B1c + linker + B2)"],
                ["existingLampLf", "LF · optional"],
                ["existingLampLb", "LB · optional"],
              ] as const
            ).map(([key, label]) => (
              <WrappedField key={key} label={label}>
                <Input
                  value={text(draft, key)}
                  onChange={(e) => set(key, e.target.value)}
                  spellCheck={false}
                  placeholder="5′→3′ DNA sequence"
                />
              </WrappedField>
            ))}
            <WrappedField
              label="FIP F1c length (nt)"
              hint="Number of 5′ target-derived F1c bases before the selected linker and F2 segment."
            >
              <Input
                type="number"
                min={1}
                value={text(draft, "existingLampFipF1cLength")}
                onChange={(e) => set("existingLampFipF1cLength", e.target.value)}
              />
            </WrappedField>
            <WrappedField
              label="BIP B1c length (nt)"
              hint="Number of 5′ target-derived B1c bases before the selected linker and B2 segment."
            >
              <Input
                type="number"
                min={1}
                value={text(draft, "existingLampBipB1cLength")}
                onChange={(e) => set("existingLampBipB1cLength", e.target.value)}
              />
            </WrappedField>
          </div>
        </div>
      ) : null}
      <EngineFields
        engine={engine}
        moduleId={moduleId}
        section="design"
        value={(key) => text(draft, key)}
        onChange={(key, next) => set(key, next)}
      />
      {moduleId === "sequencing-primer" ? (
        <BenchPanels
          template={text(draft, "template")}
          only={["check-primers"]}
          draft={draft}
          set={set}
        />
      ) : null}
      {moduleId === "lamp" ? (
        <div className="rounded-lg border border-dashed border-border/60 bg-surface-wash/20 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
          PrimerExplorer V5 and the NEB LAMP design tool remain benchmark/reference authorities, not
          hidden alternative design engines. NUPACK remains reference-only because its current
          licensing does not permit bundling it as PCRStudio&apos;s web-app backend. The executable
          design stays transparent: PCRStudio topology + Primer3 thermodynamics + independent
          validators.
        </div>
      ) : null}
    </Step>
  );
}

function StrategyStep({
  draft,
  set,
  words,
  moduleId,
  engine,
}: {
  draft: Draft;
  set: (key: string, value: string) => void;
  words: StepPlan;
  moduleId: string;
  engine: EngineId;
}) {
  if (moduleId === "inverse-pcr" || moduleId === "tiled-scheme") {
    return (
      <Step title={words.heading} description={words.description}>
        <EngineFields
          engine={engine}
          moduleId={moduleId}
          section="strategy"
          value={(key) => text(draft, key)}
          onChange={(key, next) => set(key, next)}
        />
        {moduleId === "inverse-pcr" ? (
          <BenchPanels
            template={text(draft, "template")}
            only={["enzyme"]}
            draft={draft}
            set={set}
          />
        ) : null}
      </Step>
    );
  }

  const strategy = text(draft, "colonyScreenStrategy") || "insert-specific-pair";
  if (moduleId !== "colony-pcr") {
    return (
      <Step title={words.heading} description={words.description}>
        No strategy controls.
      </Step>
    );
  }
  const needsVectorPrimer = ["vector-plus-insert", "orientation-screen"].includes(strategy);
  const unsupportedTwoVector = strategy === "two-vector-primers";
  const positive = Number(text(draft, "colonyExpectedPositiveBandBp"));
  const empty = Number(text(draft, "colonyExpectedEmptyBandBp"));
  const minDelta = Number(text(draft, "colonyMinimumResolvableDifferenceBp") || "50");
  const delta =
    Number.isFinite(positive) && Number.isFinite(empty) && positive > 0 && empty > 0
      ? Math.abs(positive - empty)
      : null;

  return (
    <Step title={words.heading} description={words.description}>
      <WrappedField
        label="Screening logic"
        hint="Choose the biological question first; primer placement is constrained by the answer the gel or endpoint readout has to distinguish."
      >
        <select
          value={strategy}
          onChange={(event) => {
            const next = event.target.value;
            set("colonyScreenStrategy", next);
            if (next === "insert-specific-pair") {
              set("vectorPrimerName", "");
              set("vectorPrimerSequence", "");
              set("vectorPrimerReadsInto", "start");
            }
          }}
          className="h-9 w-full rounded-lg border border-border/70 bg-surface-wash/35 px-3 text-sm sm:max-w-lg"
        >
          <option value="insert-specific-pair">
            Two insert-specific primers — presence/size screen
          </option>
          <option value="vector-plus-insert">
            Vector + insert primer — junction/orientation screen
          </option>
          <option value="two-vector-primers" disabled>
            Two vector primers — planned, not executable in Gen1
          </option>
          <option value="orientation-screen">
            Orientation screen — vector primer + directional insert primer
          </option>
        </select>
      </WrappedField>

      {unsupportedTwoVector ? (
        <p className="rounded-lg border border-warning/35 bg-warning/5 px-3 py-2 text-xs leading-relaxed text-warning">
          Two-vector-primer colony screening is preserved as a planned workflow identity, but the
          current flanking engine does not execute two independently fixed vector primers. Choose an
          executable strategy before running; PCRStudio will not reinterpret this as an
          insert-specific pair.
        </p>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-3">
        <WrappedField
          label="Expected positive band (bp)"
          hint="Measured/expected from the chosen screening topology, not a primer score."
        >
          <Input
            type="number"
            min={1}
            value={text(draft, "colonyExpectedPositiveBandBp")}
            onChange={(event) => set("colonyExpectedPositiveBandBp", event.target.value)}
          />
        </WrappedField>
        <WrappedField
          label="Expected empty-vector/control band (bp)"
          hint="Leave empty if the chosen strategy produces no meaningful empty-vector band."
        >
          <Input
            type="number"
            min={1}
            value={text(draft, "colonyExpectedEmptyBandBp")}
            onChange={(event) => set("colonyExpectedEmptyBandBp", event.target.value)}
          />
        </WrappedField>
        <WrappedField
          label="Minimum resolvable difference (bp)"
          hint="A bench/readout planning threshold; it does not change sequence ranking."
        >
          <Input
            type="number"
            min={1}
            value={text(draft, "colonyMinimumResolvableDifferenceBp") || "50"}
            onChange={(event) => set("colonyMinimumResolvableDifferenceBp", event.target.value)}
          />
        </WrappedField>
      </div>

      {delta !== null ? (
        <p
          className={cn(
            "rounded-lg border px-3 py-2 text-xs leading-relaxed",
            delta >= minDelta
              ? "border-success/40 bg-success/5 text-foreground"
              : "border-warning/35 bg-warning/5 text-warning",
          )}
        >
          Predicted band separation: <strong>{delta} bp</strong>.{" "}
          {delta >= minDelta
            ? "This meets the user-declared readout separation threshold."
            : "This is below the user-declared separation threshold; the screen may not distinguish the biological outcomes on the intended readout."}
        </p>
      ) : null}

      {needsVectorPrimer ? (
        <VectorPrimerPanel
          onPlace={() => placeVectorPrimersAction(text(draft, "vectorSequence"))}
          chosen={text(draft, "vectorPrimerName")}
          onChoose={(name) => set("vectorPrimerName", name)}
          own={text(draft, "vectorPrimerSequence")}
          onOwn={(sequence) => set("vectorPrimerSequence", sequence)}
          readsInto={text(draft, "vectorPrimerReadsInto")}
          onReadsInto={(side) => set("vectorPrimerReadsInto", side)}
          plasmid={text(draft, "vectorSequence")}
          onPlasmid={(sequence) => set("vectorSequence", sequence)}
        />
      ) : (
        <p className="text-xs leading-relaxed text-muted-foreground">
          This strategy keeps both primers inside the insert; no vector-primer placement is
          required.
        </p>
      )}
    </Step>
  );
}

function VectorStep({
  draft,
  set,
  words,
  canFetch,
  template,
}: {
  draft: Draft;
  set: (key: string, value: string) => void;
  words: StepPlan;
  canFetch: boolean;
  template: string;
}) {
  return (
    <Step title={words.heading} description={words.description}>
      <SequenceInput
        label="Recipient vector sequence"
        value={text(draft, "cloningVector")}
        onChange={(next) => set("cloningVector", next)}
        canFetch={canFetch}
        allowConsensus={false}
        rows={8}
        placeholder=">recipient_vector\nACGT…"
        hint="Provide the actual recipient vector/derivative, not only a vector name. PCRStudio treats it as circular unless a future explicitly modelled linear-vector branch says otherwise."
      />
      <div className="grid gap-3 sm:grid-cols-2">
        <WrappedField
          label="Vector name / revision"
          hint="Human-readable provenance for the exact recipient sequence."
        >
          <Input
            value={text(draft, "cloningVectorName")}
            onChange={(event) => set("cloningVectorName", event.target.value)}
            placeholder="pUC-derived vector, lab revision 3"
          />
        </WrappedField>
        <WrappedField
          label="Vector topology"
          hint="Gen-1 restriction-cloning construct simulation is qualified for a circular recipient vector."
        >
          <select
            value={text(draft, "cloningVectorTopology") || "circular"}
            onChange={(event) => set("cloningVectorTopology", event.target.value)}
            className="h-9 w-full rounded-lg border border-border/70 bg-surface-wash/35 px-3 text-sm"
          >
            <option value="circular">Circular recipient vector</option>
            <option value="linear" disabled>
              Linear recipient — not executable in this branch
            </option>
          </select>
        </WrappedField>
      </div>

      <div className="space-y-3 rounded-lg border border-border/60 bg-surface-wash/20 p-3">
        <WrappedField
          label="Submitted insert source"
          hint="Use the exact linear insert sequence, or explicitly extract a region from the circular submitted donor template with 0-based start + length coordinates."
        >
          <select
            value={text(draft, "circular") === "true" ? "circular-donor" : "exact-insert"}
            onChange={(event) => {
              const donor = event.target.value === "circular-donor";
              set("circular", donor ? "true" : "false");
              if (!donor) {
                set("targetStart", "");
                set("targetLength", "");
              }
            }}
            className="h-9 w-full rounded-lg border border-border/70 bg-surface-wash/35 px-3 text-sm sm:max-w-md"
          >
            <option value="exact-insert">Submitted template is the exact linear insert</option>
            <option value="circular-donor">
              Submitted template is a circular donor plasmid/genome region
            </option>
          </select>
        </WrappedField>
        {text(draft, "circular") === "true" ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <WrappedField
              label="Donor region start"
              hint="0-based coordinate on the circular submitted donor. Origin wrapping is supported."
            >
              <Input
                type="number"
                min={0}
                step={1}
                required
                value={text(draft, "targetStart")}
                onChange={(event) => set("targetStart", event.target.value)}
              />
            </WrappedField>
            <WrappedField
              label="Donor region length"
              hint="Number of bases to extract; must be 1..donor length."
            >
              <Input
                type="number"
                min={1}
                step={1}
                required
                value={text(draft, "targetLength")}
                onChange={(event) => set("targetLength", event.target.value)}
              />
            </WrappedField>
          </div>
        ) : null}
      </div>

      <div className="space-y-3 rounded-lg border border-border/60 bg-surface-wash/20 p-3">
        <h4 className="text-sm font-semibold">Coding / fusion semantics</h4>
        <p className="text-xs leading-relaxed text-muted-foreground">
          Optional protein-coding context is validated against the exact final insert. It never
          changes primer ranking. In-frame fusion is claimed only against the declared
          recipient-junction phase; final construct translation still requires independent construct
          validation.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <WrappedField
            label="Coding intent"
            hint="Choose noncoding unless this insert carries an ORF or must remain in frame with an upstream fusion."
          >
            <select
              value={text(draft, "cloningCodingIntent") || "noncoding"}
              onChange={(e) => {
                set("cloningCodingIntent", e.target.value);
                if (e.target.value === "noncoding") {
                  set("cloningCdsStart", "");
                  set("cloningCdsEnd", "");
                  set("cloningStopCodonPolicy", "not-applicable");
                  set("cloningVectorJunctionFrame", "");
                }
              }}
              className="h-9 w-full rounded-lg border border-border/70 bg-surface-wash/35 px-3 text-sm"
            >
              <option value="noncoding">Noncoding / frame not applicable</option>
              <option value="preserve-orf">Preserve insert ORF</option>
              <option value="in-frame-fusion">In-frame fusion intent</option>
            </select>
          </WrappedField>
          <WrappedField
            label="Stop-codon policy"
            hint="For remove, submit/extract an insert whose declared CDS does not include the terminal stop codon."
          >
            <select
              value={
                text(draft, "cloningStopCodonPolicy") ||
                (text(draft, "cloningCodingIntent") === "noncoding" ? "not-applicable" : "preserve")
              }
              onChange={(e) => set("cloningStopCodonPolicy", e.target.value)}
              className="h-9 w-full rounded-lg border border-border/70 bg-surface-wash/35 px-3 text-sm"
            >
              <option value="not-applicable">Not applicable</option>
              <option value="preserve">Preserve terminal stop if present</option>
              <option value="remove">Stop removed from submitted insert</option>
            </select>
          </WrappedField>
        </div>
        {text(draft, "cloningCodingIntent") &&
        text(draft, "cloningCodingIntent") !== "noncoding" ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <WrappedField
              label="CDS start"
              hint="0-based on the final insert (after donor-region extraction, if used)."
            >
              <Input
                required
                type="number"
                min={0}
                step={1}
                value={text(draft, "cloningCdsStart")}
                onChange={(e) => set("cloningCdsStart", e.target.value)}
              />
            </WrappedField>
            <WrappedField label="CDS end" hint="0-based half-open end on the final insert.">
              <Input
                required
                type="number"
                min={1}
                step={1}
                value={text(draft, "cloningCdsEnd")}
                onChange={(e) => set("cloningCdsEnd", e.target.value)}
              />
            </WrappedField>
            {text(draft, "cloningCodingIntent") === "in-frame-fusion" ? (
              <WrappedField
                label="Vector junction phase"
                hint="Number of coding bases already present in the recipient codon at the insertion junction (0, 1 or 2)."
              >
                <Input
                  required
                  type="number"
                  min={0}
                  max={2}
                  step={1}
                  value={text(draft, "cloningVectorJunctionFrame")}
                  onChange={(e) => set("cloningVectorJunctionFrame", e.target.value)}
                />
              </WrappedField>
            ) : null}
            <WrappedField
              label="Fusion tag (optional)"
              hint="Human-readable tag identity; sequence is not invented from this label."
            >
              <Input
                value={text(draft, "cloningFusionTag")}
                onChange={(e) => set("cloningFusionTag", e.target.value)}
                placeholder="e.g. His6, GFP"
              />
            </WrappedField>
            <WrappedField
              label="Linker amino acids (optional)"
              hint="Evidence/intent only; PCRStudio does not reverse-translate an amino-acid linker into DNA in this module."
            >
              <Input
                value={text(draft, "cloningLinkerAa")}
                onChange={(e) => set("cloningLinkerAa", e.target.value.toUpperCase())}
                placeholder="GGGGS"
              />
            </WrappedField>
          </div>
        ) : null}
      </div>

      <CloningTails draft={draft} set={set} onRank={() => rankEnzymesAction(template, "absent")} />

      <p className="rounded-lg border border-dashed border-border/60 bg-surface-wash/20 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
        Sequence-level recognition sites and end geometry can be checked here. Methylation
        sensitivity, star activity, supplier buffer compatibility, heat inactivation and practical
        digest/ligation efficiency remain vendor- and sample-specific bench evidence; PCRStudio does
        not infer them from the recognition sequence.
      </p>
    </Step>
  );
}

function ConstructStep({
  draft,
  set: _set,
  words,
  template,
  moduleId,
}: {
  draft: Draft;
  set: (key: string, value: string) => void;
  words: StepPlan;
  template: string;
  moduleId: string;
}) {
  if (moduleId === "gibson-assembly") {
    const fragments = text(draft, "segments")
      .split("\n")
      .map((entry) => entry.trim())
      .filter(Boolean);
    const circular = text(draft, "circular") === "true";
    const junctions =
      fragments.length > 0 ? Math.max(0, fragments.length - 1 + (circular ? 1 : 0)) : 0;
    return (
      <Step title={words.heading} description={words.description}>
        <div className="grid gap-3 sm:grid-cols-3">
          <SummaryMetric
            label="Ordered fragments"
            value={fragments.length ? String(fragments.length) : "missing"}
          />
          <SummaryMetric label="Topology" value={circular ? "Circular" : "Linear"} />
          <SummaryMetric
            label="Expected junctions"
            value={fragments.length ? String(junctions) : "unresolved"}
          />
        </div>
        <div className="rounded-lg border bg-surface-wash/25 p-3 text-xs leading-relaxed text-muted-foreground">
          This page checks the requested fragment order and topology only. Exact overlap sequences,
          supplier-ready primers and construct/junction identities are outputs of the executable
          junction engine; PCRStudio does not fabricate them before the design run.
        </div>
      </Step>
    );
  }

  if (moduleId === "site-directed-mutagenesis") {
    const originalBases = approximateBases(template);
    const kind = text(draft, "editKind");
    const toBases = approximateBases(text(draft, "editTo"));
    const replacingBases = approximateBases(text(draft, "editReplacing"));
    const expectedBases =
      !originalBases || !kind
        ? 0
        : kind === "insert"
          ? originalBases + toBases
          : kind === "delete"
            ? Math.max(0, originalBases - replacingBases)
            : kind === "substitute"
              ? Math.max(0, originalBases - replacingBases + toBases)
              : originalBases;
    return (
      <Step title={words.heading} description={words.description}>
        <div className="grid gap-3 sm:grid-cols-4">
          <SummaryMetric
            label="Original plasmid"
            value={originalBases ? `${originalBases.toLocaleString()} bp` : "missing"}
          />
          <SummaryMetric label="Edit" value={kind || "unresolved"} />
          <SummaryMetric label="Coordinate" value={text(draft, "editAt") || "unresolved"} />
          <SummaryMetric
            label="Expected length"
            value={expectedBases ? `${expectedBases.toLocaleString()} bp` : "unresolved"}
          />
        </div>
        <div className="rounded-lg border bg-surface-wash/25 p-3 text-xs leading-relaxed text-muted-foreground">
          The length preview is a deterministic check of the requested edit instruction, not a
          simulated transformation result. Exact edited sequence identity is emitted by the
          mutagenic-pair runtime after coordinate and replacement validation.
        </div>
      </Step>
    );
  }

  const vectorBases = approximateBases(text(draft, "cloningVector"));
  const insertBases = approximateBases(template);
  const ready = [
    "cloningVector",
    "forwardEnzyme",
    "reverseEnzyme",
    "forwardProtectiveSequence",
    "reverseProtectiveSequence",
  ].every((field) => text(draft, field).trim());
  return (
    <Step title={words.heading} description={words.description}>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border bg-surface-wash/25 p-3 text-xs leading-relaxed">
          <div>
            <strong>Insert:</strong>{" "}
            {insertBases ? `${insertBases.toLocaleString()} bp` : "missing"}
          </div>
          <div>
            <strong>Vector:</strong>{" "}
            {vectorBases ? `${vectorBases.toLocaleString()} bp, circular` : "missing"}
          </div>
          <div>
            <strong>Forward enzyme:</strong> {text(draft, "forwardEnzyme") || "unresolved"}
          </div>
          <div>
            <strong>Reverse enzyme:</strong> {text(draft, "reverseEnzyme") || "unresolved"}
          </div>
        </div>
        <div className="rounded-lg border bg-surface-wash/25 p-3 text-xs leading-relaxed text-muted-foreground">
          Independent pydna/Biopython simulation is advisory and sequence-level. It can verify a
          represented digest/ligation topology but cannot prove methylation state, star activity,
          enzyme activity in the selected buffer, ligation efficiency or transformant recovery.
        </div>
      </div>
      {!ready ? (
        <p className="text-xs text-warning">
          Complete vector, both enzymes and both explicit protective sequences before construct
          simulation can be attempted.
        </p>
      ) : (
        <p className="text-xs leading-relaxed text-muted-foreground">
          Inputs are complete for construct-level preflight. The executable independent simulation
          result is attached after the primer design run, when the exact supplier-ready tailed pair
          is known; PCRStudio does not fabricate an amplified product before Primer3 selects the
          annealing halves.
        </p>
      )}
    </Step>
  );
}

function ConstraintsStep({
  draft,
  set,
  presets,
  words,
  moduleId,
}: {
  draft: Draft;
  set: (key: string, value: string) => void;
  presets: Presets;
  words: StepPlan;
  moduleId: string;
}) {
  const chosen = presets.purposes.find((entry) => entry.id === text(draft, "purpose"));

  /*
   * The grey number in each box is what the run will actually use, which means
   * mirroring the worker's own layering rather than approximating it.
   *
   * `pipeline.py` builds its limits as `{**intent.constraints,
   * **constraint_defaults, **supplied}` — the purpose first, the assay over the
   * top of it, and what somebody typed over both. So the assay wins over the
   * purpose here, in that order, because that is the order the run resolves.
   *
   * This layer was missing entirely: the placeholder followed the purpose and
   * fell through to the engine's bare default, so long-range PCR showed
   * "shortest product 200" for an assay that runs at 5000. A form that shows
   * one number while the run uses another is worse than a form showing none.
   */
  const fallback = (name: string) =>
    presets.assay?.constraints[name] ?? chosen?.constraints[name] ?? undefined;

  return (
    <Step title={words.heading} description={words.description}>
      {presets.purposes.length ? (
        <FieldGroup label="What is the product for?" hint={chosen?.summary}>
          <div className="flex flex-wrap gap-1.5">
            {presets.purposes.map((entry) => {
              const active = entry.id === text(draft, "purpose");
              return (
                <button
                  key={entry.id}
                  type="button"
                  aria-pressed={active}
                  onClick={() => set("purpose", entry.id)}
                  className={cn(
                    "rounded-full border px-3 py-1 text-xs transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                    active
                      ? "border-primary bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-surface-warm/45 hover:text-foreground",
                  )}
                >
                  {entry.name}
                </button>
              );
            })}
          </div>
        </FieldGroup>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {presets.fields
          .filter(
            (entry) =>
              !(
                moduleId === "restriction-cloning" &&
                ["product_min", "product_max"].includes(entry.name)
              ),
          )
          .map((entry) => {
            const key = `${CONSTRAINT_PREFIX}${entry.name}`;
            return (
              <div key={entry.name} className="space-y-1.5">
                <Label htmlFor={key} className="text-xs font-medium">
                  {entry.label}
                </Label>
                <Input
                  id={key}
                  type="number"
                  step="any"
                  value={text(draft, key)}
                  onChange={(event) => set(key, event.target.value)}
                  placeholder={String(fallback(entry.name) ?? entry.default ?? "")}
                />
                {entry.hint ? (
                  <p className="text-xs leading-snug text-muted-foreground">{entry.hint}</p>
                ) : null}
              </div>
            );
          })}
      </div>

      {presets.fields.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          This module published no settings, which usually means the core is not answering.
        </p>
      ) : null}
    </Step>
  );
}

/**
 * The enzyme to start a new project with, and where the choice came from.
 *
 * Three sources, in this order, and the order is the whole point.
 *
 * **What the assay pins.** Long-range PCR pins the long-range mix; restriction
 * cloning pins a proofreading enzyme. Those are not preferences, they are what
 * the assay is — a long-range reaction run on standard Taq is not long-range
 * PCR with a different buffer, it is a reaction that stops after two kilobases.
 * So a pin wins over anything a person has said about their bench.
 *
 * Measured before this existed: the form seeded `presets.polymerases[0]`,
 * which is `taq-standard` for every engine, and sent it on every run. No
 * profile's pinned enzyme had ever reached the worker from the web interface.
 *
 * **What the person keeps on their bench.** Only where the assay is neutral,
 * and only where it offers the enzyme at all.
 *
 * **The engine's own first offering.** The fallback, and nothing more.
 */

function ReactionStep({
  draft,
  set,
  presets,
  seeded,
  words,
  engine,
  moduleId,
}: {
  draft: Draft;
  set: (key: string, value: string) => void;
  presets: Presets;
  /** What the starting enzyme was, and which of the three sources chose it. */
  seeded: { id: string | undefined; from: "assay" | "preference" | "engine" };
  words: StepPlan;
  engine: EngineId;
  moduleId: string;
}) {
  const chosen = presets.polymerases.find((entry) => entry.id === text(draft, "polymerase"));

  return (
    <Step title={words.heading} description={words.description}>
      <EngineFields
        engine={engine}
        moduleId={moduleId}
        section="reaction"
        value={(key) => text(draft, key)}
        onChange={(key, next) => set(key, next)}
      />

      <WrappedField label="Thermodynamic screening context">
        <select
          value={text(draft, "polymerase")}
          onChange={(event) => set("polymerase", event.target.value)}
          className="h-9 w-full rounded-lg border border-border/70 bg-surface-wash/35 px-3 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none sm:max-w-sm"
        >
          {presets.polymerases.map((entry) => (
            <option key={entry.id} value={entry.id}>
              {entry.name}
            </option>
          ))}
        </select>
      </WrappedField>

      {/*
       * Why the list is short, where it is.
       *
       * Every assay used to offer every enzyme, so a LAMP design could be run
       * with a proofreading polymerase — which produces nothing at all,
       * because that reaction never heats the template apart and that enzyme
       * cannot open it. Narrowing the list fixes the run and creates a new
       * question: somebody who came here knowing which enzyme they use needs
       * to be told it is not offered, and told why, rather than left to wonder
       * whether the catalogue is simply small.
       */}
      {(presets.assay?.enzyme ?? []).map((need) => (
        <p
          key={need.need}
          className="rounded-lg border border-dashed border-border/60 bg-surface-wash/25 px-3 py-2 text-xs leading-relaxed text-muted-foreground"
        >
          {need.why}
        </p>
      ))}

      {/*
       * Where this enzyme came from, said out loud, and only while it is still
       * the one that was chosen for you.
       *
       * A default that quietly differs from the engine's is the kind of thing
       * somebody discovers from a result they cannot reproduce. The two cases
       * read differently on purpose: an assay pinning an enzyme is telling you
       * something about the reaction, and a preference applying is telling you
       * something about your account.
       */}
      {seeded.id === text(draft, "polymerase") && seeded.from !== "engine" ? (
        <p className="text-xs leading-relaxed text-muted-foreground">
          {seeded.from === "assay"
            ? "Chosen by this assay, which is run with this enzyme. Changing it changes what the assay is, not only what the numbers were computed under."
            : `Chosen from your account preference. This assay does not ask for a particular enzyme, so what you keep on your bench decides.`}
        </p>
      ) : null}

      {chosen ? (
        <div className="space-y-2 rounded-xl border border-border/60 bg-surface-wash/30 p-3">
          <p className="text-sm leading-relaxed">{chosen.summary}</p>
          <dl className="grid gap-x-6 gap-y-1 text-xs sm:grid-cols-4">
            <Small label="Monovalent" value={`${chosen.reaction.mv_conc} mM`} />
            <Small label="Divalent" value={`${chosen.reaction.dv_conc} mM`} />
            <Small label="dNTP, all four" value={`${chosen.reaction.dntp_conc} mM`} />
            <Small label="Tm oligo input" value={`${chosen.reaction.dna_conc} nM`} />
          </dl>
          <p className="text-xs leading-snug text-muted-foreground">
            dNTP here is the sum of all four, not the concentration of each — 0.2 mM per base is
            0.8. Every melting temperature in the result is computed under these numbers.
          </p>
        </div>
      ) : null}

      {/*
       * Calculation context is visible but not anonymously editable in the
       * Scientific-Strict release path. Salt/Mg/dNTP/oligo concentration can
       * change thermodynamic predictions in non-monotonic ways, so a material
       * change belongs in a sourced, versioned chemistry profile rather than
       * in an unlabeled per-run override.
       */}
      {chosen ? (
        <p className="rounded-lg border border-dashed border-border/60 bg-surface-wash/20 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
          This is PCRStudio&apos;s versioned computational screening context, not a reconstruction
          of the named vendor kit or master mix selected above. Scientific-Strict mode does not
          accept anonymous salt, Mg²⁺, dNTP or oligo-concentration changes: a materially different
          calculation condition requires its own sourced, versioned profile.
        </p>
      ) : null}
    </Step>
  );
}

function SpecificityStep({
  draft,
  set,
  canFetch,
  words,
  engine,
  moduleId,
}: {
  draft: Draft;
  set: (key: string, value: string) => void;
  canFetch: boolean;
  words: StepPlan;
  engine: EngineId;
  moduleId: string;
}) {
  const lampConservationAware =
    moduleId === "lamp" && text(draft, "lampDesignIntent") === "panel-conservation-aware";
  const lampInclusivityMissing = lampConservationAware && !text(draft, "inclusivity").trim();

  return (
    <Step title={words.heading} description={words.description}>
      <SequenceInput
        label="Background"
        value={text(draft, "background")}
        onChange={(next) => set("background", next)}
        canFetch={canFetch}
        rows={7}
        // A background is checked against rather than designed from, so several
        // records are exactly right and collapsing them would be wrong.
        allowConsensus={false}
        placeholder=">pUC19&#10;TCGCGCGTTTCGGTGATGACGGTGAAAACCTCTGACACATGCAGCTCCCGGAGACGGTCACAGCTTGTCTGT…"
        hint="Several records are welcome here: a vector and a host genome can go in together."
      />

      {moduleId === "lamp" ? (
        <div
          className={
            lampInclusivityMissing
              ? "rounded-lg border border-destructive/40 bg-destructive/5 p-3"
              : ""
          }
        >
          <SequenceInput
            label={
              lampConservationAware
                ? "Target inclusivity / conservation panel · required"
                : "Target inclusivity / conservation panel · optional"
            }
            value={text(draft, "inclusivity")}
            onChange={(next) => set("inclusivity", next)}
            canFetch={canFetch}
            rows={7}
            allowConsensus={false}
            canAlign
            placeholder={
              ">target-isolate-1 accession.version\nACGT…\n>target-isolate-2 accession.version\nACGA…"
            }
            hint={
              lampConservationAware
                ? "Required by Panel conservation-aware design. PCRStudio aligns the explicit intended-target panel and lets conservation evidence participate in candidate ranking. Keep accession/version and isolate context in FASTA headers where available."
                : "Optional in Standard design. The supplied intended-target panel is audited for inclusivity/coverage but does not alter sequence ranking unless Design intent is explicitly set to Panel conservation-aware."
            }
          />
          {lampInclusivityMissing ? (
            <p role="alert" className="mt-2 text-xs text-destructive">
              Panel conservation-aware LAMP cannot run until an explicit intended-target panel is
              supplied here.
            </p>
          ) : null}
        </div>
      ) : null}

      {moduleId === "species-specific-pcr" ? (
        <>
          <SequenceInput
            label="Target inclusivity panel"
            value={text(draft, "inclusivity")}
            onChange={(next) => set("inclusivity", next)}
            canFetch={canFetch}
            rows={6}
            allowConsensus={false}
            placeholder=">target-strain-1\nACGT…\n>target-strain-2\nACGA…"
            hint="Required in Scientific-Strict: provide explicit FASTA records representing the intended target inclusivity panel. Preserve accession/version, isolate/strain and taxonomy context in FASTA headers where available. Every returned pair must form a sequence-compatible product on every supplied record; the recorded SHA-256 identifies the submitted panel content, not taxonomic completeness or empirical inclusivity."
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <WrappedField
              label="Inclusivity-panel provenance"
              hint="Required: database/release or isolate source, accession/version policy and retrieval/review date. FASTA labels alone are not treated as biological identity authority."
            >
              <Input
                required
                value={text(draft, "inclusivityPanelProvenance")}
                onChange={(event) => set("inclusivityPanelProvenance", event.target.value)}
                placeholder="e.g. NCBI RefSeq release/date + accession.version list / curated isolate collection"
              />
            </WrappedField>
            <WrappedField
              label="Exclusivity-panel provenance"
              hint="Required: source/release and traceable identity for the near-neighbour/background panel used for the claim."
            >
              <Input
                required
                value={text(draft, "backgroundPanelProvenance")}
                onChange={(event) => set("backgroundPanelProvenance", event.target.value)}
                placeholder="e.g. NCBI RefSeq release/date + curated near-neighbour accessions"
              />
            </WrappedField>
          </div>
          <WrappedField
            label="Panel-selection rationale"
            hint="Required: explain how target diversity and closely related/co-occurring non-targets were chosen. This is the reviewable biological scope of the specificity claim."
          >
            <Input
              required
              value={text(draft, "speciesPanelSelectionRationale")}
              onChange={(event) => set("speciesPanelSelectionRationale", event.target.value)}
              placeholder="Temporal/geographic/phylogenetic target diversity; closest taxa and likely co-occurring non-targets"
            />
          </WrappedField>
          <div className="space-y-3 rounded-lg border border-border/60 bg-surface-wash/20 p-3">
            <div>
              <h4 className="text-sm font-semibold">Reproducible species-panel snapshot</h4>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                Pin taxonomy and sequence-database authority plus the exact accession.version
                manifest. PCRStudio records and hashes this declaration; it does not infer taxonomic
                completeness or independently resolve the TaxID from FASTA labels.
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <WrappedField
                label="Target TaxID"
                hint="Required positive NCBI Taxonomy identifier for the intended target scope."
              >
                <Input
                  required
                  type="number"
                  min={1}
                  step={1}
                  value={text(draft, "speciesTargetTaxid")}
                  onChange={(event) => set("speciesTargetTaxid", event.target.value)}
                  placeholder="e.g. 562"
                />
              </WrappedField>
              <WrappedField
                label="Panel retrieval / review date"
                hint="Required ISO date for this pinned panel snapshot."
              >
                <Input
                  required
                  type="date"
                  value={text(draft, "speciesPanelRetrievedDate")}
                  onChange={(event) => set("speciesPanelRetrievedDate", event.target.value)}
                />
              </WrappedField>
              <WrappedField
                label="Taxonomy snapshot"
                hint="Authority/release/date used to assign the declared taxonomic scope."
              >
                <Input
                  required
                  value={text(draft, "speciesTaxonomySnapshot")}
                  onChange={(event) => set("speciesTaxonomySnapshot", event.target.value)}
                  placeholder="NCBI Taxonomy snapshot / release date"
                />
              </WrappedField>
              <WrappedField
                label="Sequence database snapshot"
                hint="Database name, release/build and date used to curate target and near-neighbour records."
              >
                <Input
                  required
                  value={text(draft, "speciesDatabaseSnapshot")}
                  onChange={(event) => set("speciesDatabaseSnapshot", event.target.value)}
                  placeholder="NCBI RefSeq release/date or curated database build"
                />
              </WrappedField>
            </div>
            <WrappedField
              label="Accession.version manifest"
              hint="Required exact accession.version list for the reviewed inclusivity/exclusivity panel. This text is SHA-256 hashed into the result."
            >
              <textarea
                required
                rows={5}
                spellCheck={false}
                className="w-full rounded-lg border border-border/70 bg-background px-3 py-2 font-mono text-xs"
                value={text(draft, "speciesPanelAccessionManifest")}
                onChange={(event) => set("speciesPanelAccessionManifest", event.target.value)}
                placeholder={`INCLUSIVITY\nNC_000000.1\n...\nEXCLUSIVITY\nNC_000001.2`}
              />
            </WrappedField>
            <WrappedField
              label="Accession authority snapshot"
              hint="Required offline resolver TSV: accession.version, TaxID, lifecycle status (current/suppressed/replaced), optional replacement accession, optional sequence-database snapshot and taxonomy snapshot. Suppressed/replaced accessions fail closed instead of being silently accepted."
            >
              <textarea
                required
                rows={5}
                spellCheck={false}
                className="w-full rounded-lg border border-border/70 bg-background px-3 py-2 font-mono text-xs"
                value={text(draft, "speciesPanelAccessionAuthorityManifest")}
                onChange={(event) =>
                  set("speciesPanelAccessionAuthorityManifest", event.target.value)
                }
                placeholder={`NC_000000.1\t562\tcurrent\t\tRefSeq-2026-09\tNCBI-Taxonomy-2026-09`}
              />
            </WrappedField>
            <WrappedField
              label="Record metadata manifest"
              hint="Required one-row-per-FASTA-record TSV: record_id, accession.version, inclusivity/exclusivity role, topology, optional relative weight and optional population/group label. This evidence is hashed separately and never relaxes all-record coverage gates."
            >
              <textarea
                required
                rows={5}
                spellCheck={false}
                className="w-full rounded-lg border border-border/70 bg-background px-3 py-2 font-mono text-xs"
                value={text(draft, "speciesPanelRecordMetadataManifest")}
                onChange={(event) => set("speciesPanelRecordMetadataManifest", event.target.value)}
                placeholder={`targetA\tNC_000000.1\tinclusivity\tcircular\t1\tcore\nnear1\tNC_000001.2\texclusivity\tlinear\t\tnear-neighbour`}
              />
            </WrappedField>
          </div>
        </>
      ) : null}

      {engine === "flanking-pair" ? (
        <div className="grid gap-4 sm:grid-cols-2">
          <WrappedField
            label="Whole-primer mismatch budget"
            hint={
              moduleId === "species-specific-pcr"
                ? "Scientific-Strict uses the versioned species-specific value of 3 mismatches; changing it requires a separately reviewed specificity method."
                : "Maximum definite mismatches allowed anywhere in the ungapped primer window during the bounded sequence screen. This is a screening envelope, not proof of extension."
            }
          >
            <Input
              type="number"
              min={0}
              max={20}
              value={text(draft, "maxMismatches")}
              onChange={(event) => set("maxMismatches", event.target.value)}
              disabled={moduleId === "species-specific-pcr"}
            />
          </WrappedField>
        </div>
      ) : null}

      {engine === "flanking-pair" || moduleId === "lamp" ? (
        <div className="rounded-lg border border-dashed border-border/60 bg-surface-wash/20 p-3">
          <p className="text-xs font-medium">Independent external confirmation · manual handoff</p>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            PCRStudio does not submit your sequences to these services. Open them only when you want
            an additional external reference check; their databases, versions and claim scope remain
            separate from the local MFEprimer/BLAST evidence recorded in this run.
          </p>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
            <a
              href="https://www.ncbi.nlm.nih.gov/tools/primer-blast/"
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-2"
            >
              NCBI Primer-BLAST
            </a>
            {moduleId !== "lamp" ? (
              <a
                href="https://genome.ucsc.edu/cgi-bin/hgPcr"
                target="_blank"
                rel="noopener noreferrer"
                className="underline underline-offset-2"
              >
                UCSC In-Silico PCR
              </a>
            ) : null}
            {moduleId === "lamp" ? (
              <a
                href="https://www.nupack.org/"
                target="_blank"
                rel="noopener noreferrer"
                className="underline underline-offset-2"
              >
                NUPACK · reference only
              </a>
            ) : null}
          </div>
          {moduleId === "lamp" ? (
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              Primer-BLAST is a pair-level reference and does not validate full six-region LAMP
              topology. NUPACK is intentionally not bundled or called by the PCRStudio backend;
              current licensing and the need for an assay-specific multi-strand interpretation keep
              it reference-only in Gen1.
            </p>
          ) : null}
        </div>
      ) : null}

      <p className="text-xs leading-relaxed text-muted-foreground">
        Specificity v5 uses mismatch-complete ungapped discovery across the whole primer. It does
        not hide a site because a terminal 3&prime; base mismatches or because a duplex misses an
        arbitrary ΔG cutoff. Terminal mismatches and IUPAC ambiguity remain evidence for review;
        this bounded supplied-sequence screen is not a claim of experimental extension or
        whole-database uniqueness.
      </p>
    </Step>
  );
}

function ReviewStep({
  draft,
  set,
  presets,
  bases,
  engine,
  segments,
  pending,
  job,
  activeJob,
  startingRun,
  cancellingRun,
  cancelCurrentRun,
  runnable,
  ready,
  missingRequirements,
  plan,
  words,
  moduleId,
}: {
  draft: Draft;
  set: (key: string, value: string) => void;
  presets: Presets;
  bases: number;
  engine: EngineId;
  segments: number;
  pending: boolean;
  job: RunJob | null;
  activeJob: boolean;
  startingRun: boolean;
  cancellingRun: boolean;
  cancelCurrentRun: () => Promise<void>;
  plan: PagePlan;
  words: StepPlan;
  runnable: boolean;
  ready: boolean;
  missingRequirements: string[];
  moduleId: string;
}) {
  const isAssembly = engine === "junction-primers";
  const reaction = presets.polymerases.find((entry) => entry.id === text(draft, "polymerase"));
  const intent = presets.purposes.find((entry) => entry.id === text(draft, "purpose"));
  const protocolMeta = NAMED_PROTOCOL_FIELDS[moduleId];
  const protocolValue = protocolMeta ? text(draft, protocolMeta.field) : "";
  const baseline = { ...BLANK, ...(plan.initial ?? {}), ...(plan.fixed ?? {}) };
  const workflowEvidenceFields = [
    "colonyExpectedPositiveBandBp",
    "colonyExpectedEmptyBandBp",
    "colonyMinimumResolvableDifferenceBp",
    "colonyScreenStrategy",
    "qpcrStandardCurveSlope",
    "qpcrStandardCurveR2",
    "qpcrEfficiencyPercent",
    "qpcrLod",
    "qpcrLloq",
    "qpcrUloq",
    "qpcrReplicates",
    "qpcrCqMean",
    "qpcrDynamicRangeLogs",
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
    "dpcrThresholdMethod",
    "dpcrValidationNotes",
    "dpcrInstrumentSoftwareVersion",
    "dpcrPartitionVolumeAuthority",
    "dpcrPlateLot",
    "dpcrVpf",
    "dpcrControlStatus",
    "dpcrRainPolicy",
    "dpcrRawDataReference",
    "rpaScreenCandidateCount",
    "rpaScreenReplicates",
    "rpaScreenResponse",
    "rpaScreenControls",
    "rpaScreenNotes",
    "lampValidationSetCount",
    "lampValidationReplicates",
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
  ];
  const moduleStructuredFields: Record<string, string[]> = {
    "nested-pcr": ["shares", "margin", "singleTube", "carryoverPrevention"],
    "inverse-pcr": [
      "inverseBranch",
      "enzyme",
      "methylationBranch",
      "leftEndPhosphate",
      "rightEndPhosphate",
      "circularizationProvenance",
      "linearControlProvenance",
      "unknownFlankMin",
      "unknownFlankMax",
    ],
    "qpcr-probe": ["probeProtocol"],
    "arms-pcr": ["at", "alleleOne", "alleleTwo", "geometry"],
    kasp: [
      "at",
      "alleleOne",
      "alleleTwo",
      "geometry",
      "kaspAssayMode",
      "kaspProtocol",
      "kaspPlateFormat",
      "kaspInstrumentModel",
      "kaspRoxPolicy",
    ],
    "tetra-primer-arms": ["at", "alleleOne", "alleleTwo", "geometry", "tetraMinBandSeparationBp"],
    "universal-primers": ["alignmentMode", "tailForward", "tailReverse"],
    "sequencing-primer": [
      "direction",
      "deadZone",
      "readLength",
      "sequencingInstrument",
      "sequencingInstrumentName",
      "sequencingFacilitySop",
      "sequencingProtocol",
    ],
    race: [
      "raceDirection",
      "raceSubstrate",
      "racePreparation",
      "raceRound",
      "raceAdapter",
      "racePartnerSequence",
    ],
    "tiled-scheme": [
      "tilingOperation",
      "tilingAlignmentMode",
      "overlap",
      "pools",
      "panelMode",
      "existingBed",
      "schemeConfig",
      "regionBed",
      "primerName",
    ],
    "gibson-assembly": ["segments", "circular", "method", "assemblyProtocol"],
    "site-directed-mutagenesis": [
      "editKind",
      "editAt",
      "editTo",
      "editReplacing",
      "postAmplificationProtocol",
    ],
  };
  const structuredFields = new Set([
    protocolMeta?.field ?? "",
    ...(moduleId === "lamp"
      ? [
          "lampReadout",
          "lampReadoutChemistry",
          "lampSampleMatrix",
          "lampSamplePreparation",
          "lampFormulation",
          "lampConfirmationMode",
          "lampDetectionTopology",
          "lampDesignIntent",
          "lampLoopPolicy",
        ]
      : []),
    ...(moduleId === "colony-pcr"
      ? ["colonyHostClass", "colonyPreparation", "colonyProtocolName", "colonyProtocolProvenance"]
      : []),
    ...(moduleId === "digital-pcr"
      ? [
          "digitalPartitionFormat",
          "digitalPlatformId",
          "digitalPlatformName",
          "digitalFragmentationState",
        ]
      : []),
    ...(moduleId === "restriction-cloning"
      ? [
          "cloningVector",
          "cloningVectorName",
          "cloningVectorTopology",
          "forwardEnzyme",
          "reverseEnzyme",
          "forwardProtectiveSequence",
          "reverseProtectiveSequence",
          "tailProtocol",
        ]
      : []),
    ...(moduleStructuredFields[moduleId] ?? []),
    ...workflowEvidenceFields,
  ]);
  const overridden = Object.entries(draft).filter(([key, value]) => {
    if (
      !value ||
      ["name", "template", "background", "polymerase", "purpose", "label", "howMany"].includes(key)
    )
      return false;
    if (structuredFields.has(key)) return false;
    if (Object.prototype.hasOwnProperty.call(baseline, key) && baseline[key] === value)
      return false;
    return true;
  });
  const assayDetails: Array<{ label: string; value: string }> = [];
  if (moduleId === "colony-pcr") {
    const strategyLabels: Record<string, string> = {
      "insert-specific-pair": "Two insert-specific primers — presence/size screen",
      "vector-plus-insert": "Vector + insert primer — junction/orientation screen",
      "orientation-screen": "Orientation screen — vector primer + directional insert primer",
      "two-vector-primers": "Two vector primers — planned, not executable in Gen1",
    };
    assayDetails.push(
      {
        label: "Screen strategy",
        value: strategyLabels[text(draft, "colonyScreenStrategy")] || "not selected",
      },
      {
        label: "Expected positive band",
        value: text(draft, "colonyExpectedPositiveBandBp")
          ? `${text(draft, "colonyExpectedPositiveBandBp")} bp`
          : "not recorded",
      },
      {
        label: "Expected empty/control band",
        value: text(draft, "colonyExpectedEmptyBandBp")
          ? `${text(draft, "colonyExpectedEmptyBandBp")} bp`
          : "not recorded",
      },
      {
        label: "Minimum resolvable difference",
        value: text(draft, "colonyMinimumResolvableDifferenceBp")
          ? `${text(draft, "colonyMinimumResolvableDifferenceBp")} bp`
          : "not recorded",
      },
      {
        label: "Host class",
        value: humanChoice("colonyHostClass", text(draft, "colonyHostClass")),
      },
      {
        label: "Template preparation",
        value: humanChoice("colonyPreparation", text(draft, "colonyPreparation")),
      },
      { label: "Colony SOP", value: text(draft, "colonyProtocolName") || "not provided" },
      { label: "SOP provenance", value: text(draft, "colonyProtocolProvenance") || "not provided" },
    );
  }
  if (moduleId === "digital-pcr") {
    assayDetails.push(
      {
        label: "Partition format",
        value: humanChoice("digitalPartitionFormat", text(draft, "digitalPartitionFormat")),
      },
      {
        label: "Platform",
        value:
          text(draft, "digitalPlatformName") ||
          humanChoice("digitalPlatformId", text(draft, "digitalPlatformId")),
      },
      {
        label: "Fragmentation",
        value: humanChoice("digitalFragmentationState", text(draft, "digitalFragmentationState")),
      },
    );
  }
  if (moduleId === "lamp") {
    assayDetails.push(
      {
        label: "Workflow mode",
        value:
          text(draft, "assayMode") === "evaluate"
            ? "Validate existing LAMP set"
            : "Design new LAMP set",
      },
      {
        label: "Geometry profile",
        value: humanChoice("lampGeometryProfile", text(draft, "lampGeometryProfile")),
      },
      {
        label: "FIP/BIP junction",
        value: humanChoice("lampInnerLinker", text(draft, "lampInnerLinker")),
      },
      {
        label: "Design intent",
        value: humanChoice("lampDesignIntent", text(draft, "lampDesignIntent")),
      },
      {
        label: "Loop architecture",
        value: humanChoice("lampLoopPolicy", text(draft, "lampLoopPolicy")),
      },
      {
        label: "Specimen / preparation",
        value: [
          humanChoice("lampSampleMatrix", text(draft, "lampSampleMatrix")),
          humanChoice("lampSamplePreparation", text(draft, "lampSamplePreparation")),
        ].join(" · "),
      },
      {
        label: "Formulation",
        value: humanChoice("lampFormulation", text(draft, "lampFormulation")),
      },
      {
        label: "Readout chemistry",
        value: humanChoice("lampReadoutChemistry", text(draft, "lampReadoutChemistry")),
      },
      {
        label: "Confirmation",
        value: humanChoice("lampConfirmationMode", text(draft, "lampConfirmationMode")),
      },
    );
  }
  if (moduleId === "restriction-cloning") {
    assayDetails.push(
      {
        label: "Recipient vector",
        value:
          text(draft, "cloningVectorName") ||
          (text(draft, "cloningVector") ? "sequence supplied" : "not supplied"),
      },
      { label: "Vector topology", value: text(draft, "cloningVectorTopology") || "unresolved" },
      { label: "Forward enzyme", value: text(draft, "forwardEnzyme") || "unresolved" },
      { label: "Reverse enzyme", value: text(draft, "reverseEnzyme") || "unresolved" },
      { label: "Tail protocol", value: text(draft, "tailProtocol") || "unresolved" },
    );
  }
  if (moduleId === "nested-pcr") {
    assayDetails.push(
      { label: "Shared-primer policy", value: text(draft, "shares") || "unresolved" },
      {
        label: "Minimum inward margin",
        value: text(draft, "margin") ? `${text(draft, "margin")} bp` : "unresolved",
      },
      {
        label: "Tube topology",
        value:
          text(draft, "singleTube") === "true"
            ? "Single-tube · not executable"
            : "Two physically separate rounds",
      },
      { label: "Carry-over prevention", value: text(draft, "carryoverPrevention") || "unresolved" },
    );
  }
  if (moduleId === "inverse-pcr") {
    assayDetails.push(
      { label: "Preparation branch", value: text(draft, "inverseBranch") || "unresolved" },
      { label: "Restriction enzyme", value: text(draft, "enzyme") || "unresolved" },
      { label: "Methylation branch", value: text(draft, "methylationBranch") || "unresolved" },
      {
        label: "Circularisation provenance",
        value: text(draft, "circularizationProvenance") || "not provided",
      },
    );
  }
  if (["arms-pcr", "kasp", "tetra-primer-arms"].includes(moduleId)) {
    assayDetails.push(
      { label: "Variant coordinate", value: text(draft, "at") || "unresolved" },
      {
        label: "Alleles",
        value:
          text(draft, "alleleOne") && text(draft, "alleleTwo")
            ? `${text(draft, "alleleOne")} / ${text(draft, "alleleTwo")}`
            : "unresolved",
      },
      { label: "Geometry", value: text(draft, "geometry") || "unresolved" },
    );
    if (moduleId === "tetra-primer-arms")
      assayDetails.push({
        label: "Readout resolution",
        value: text(draft, "tetraMinBandSeparationBp")
          ? `${text(draft, "tetraMinBandSeparationBp")} bp`
          : "unresolved",
      });
    if (moduleId === "kasp")
      assayDetails.push(
        { label: "KASP protocol", value: text(draft, "kaspProtocol") || "unresolved" },
        {
          label: "Plate / instrument",
          value:
            [text(draft, "kaspPlateFormat"), text(draft, "kaspInstrumentModel")]
              .filter(Boolean)
              .join(" · ") || "unresolved",
        },
      );
  }
  if (moduleId === "universal-primers") {
    assayDetails.push({
      label: "Alignment authority",
      value: text(draft, "alignmentMode") || "unresolved",
    });
  }
  if (moduleId === "sequencing-primer") {
    assayDetails.push(
      {
        label: "Read geometry",
        value: `${text(draft, "direction") || "?"} · dead zone ${text(draft, "deadZone") || "?"} bp · usable ${text(draft, "readLength") || "?"} bp`,
      },
      {
        label: "Provider / instrument",
        value:
          text(draft, "sequencingInstrumentName") ||
          text(draft, "sequencingInstrument") ||
          "unresolved",
      },
      {
        label: "Cycle-sequencing chemistry",
        value: text(draft, "sequencingProtocol") || "unresolved",
      },
    );
  }
  if (moduleId === "race") {
    assayDetails.push(
      { label: "RACE direction", value: text(draft, "raceDirection") || "unresolved" },
      {
        label: "Substrate / preparation",
        value:
          [text(draft, "raceSubstrate"), text(draft, "racePreparation")]
            .filter(Boolean)
            .join(" · ") || "unresolved",
      },
      {
        label: "Partner / round",
        value:
          [text(draft, "raceAdapter"), text(draft, "raceRound")].filter(Boolean).join(" · ") ||
          "unresolved",
      },
    );
  }
  if (moduleId === "tiled-scheme") {
    assayDetails.push(
      { label: "Lifecycle operation", value: text(draft, "tilingOperation") || "unresolved" },
      { label: "Alignment authority", value: text(draft, "tilingAlignmentMode") || "unresolved" },
      { label: "Pools", value: text(draft, "pools") || "inherited / unresolved" },
    );
  }
  if (moduleId === "gibson-assembly") {
    assayDetails.push(
      { label: "Fragment order", value: `${segments} fragment${segments === 1 ? "" : "s"}` },
      {
        label: "Construct topology",
        value: text(draft, "circular") === "true" ? "Circular" : "Linear",
      },
      { label: "Assembly authority", value: text(draft, "assemblyProtocol") || "neb-e5510" },
    );
  }
  if (moduleId === "site-directed-mutagenesis") {
    assayDetails.push(
      {
        label: "Requested edit",
        value:
          [text(draft, "editKind"), text(draft, "editAt") && `at ${text(draft, "editAt")}`]
            .filter(Boolean)
            .join(" ") || "unresolved",
      },
      { label: "Replacement / insertion", value: text(draft, "editTo") || "none" },
      { label: "Replacing / deleting", value: text(draft, "editReplacing") || "none" },
      {
        label: "Recovery workflow",
        value: text(draft, "postAmplificationProtocol") || "unresolved",
      },
    );
  }

  const evidenceRecorded = workflowEvidenceFields.filter((field) =>
    text(draft, field).trim(),
  ).length;
  if (["qpcr-sybr", "digital-pcr", "rpa", "lamp", "colony-pcr"].includes(moduleId)) {
    assayDetails.push({
      label: "Workflow evidence",
      value: evidenceRecorded
        ? `${evidenceRecorded} field${evidenceRecorded === 1 ? "" : "s"} recorded · no sequence-ranking impact`
        : "none recorded",
    });
  }

  return (
    <Step title={words.heading} description={words.description}>
      <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
        <Small
          label={isAssembly ? "Assembly plan" : "Sequence"}
          value={
            isAssembly
              ? `${segments} fragment${segments === 1 ? "" : "s"}`
              : bases
                ? `${count(bases)} bases`
                : "none pasted"
          }
        />
        <Small label="Called" value={text(draft, "name") || "from the FASTA header"} />
        <Small label="For" value={intent?.name ?? "no particular use"} />
        <Small
          label={isAssembly ? "Joining chemistry" : "Computational context"}
          value={
            isAssembly ? text(draft, "method") || "not chosen" : (reaction?.name ?? "not chosen")
          }
        />
        {protocolMeta ? (
          <Small
            label={protocolMeta.label}
            value={humanChoice(protocolMeta.field, protocolValue)}
          />
        ) : null}
        {moduleId === "lamp" ? (
          <Small
            label="LAMP readout"
            value={humanChoice("lampReadout", text(draft, "lampReadout"))}
          />
        ) : null}
        {assayDetails.map((item) => (
          <Small key={item.label} label={item.label} value={item.value} />
        ))}
        {!isAssembly ? (
          <Small
            label="Background"
            value={
              approximateBases(text(draft, "background"))
                ? `${count(approximateBases(text(draft, "background")))} bases`
                : "none supplied — no external/background scan"
            }
          />
        ) : null}
        {/* Nothing here says "pairs" for a scheme, and nothing says it at all
            where the engine takes no such number — that line was a fabrication
            on a Gibson review, which returns one plan. */}
        {plan.unit.how ? (
          <Small
            label={`${plan.unit.many[0]!.toUpperCase()}${plan.unit.many.slice(1)} wanted`}
            value={text(draft, "howMany") || "5"}
          />
        ) : null}
        <Small
          label="Settings changed from default"
          value={overridden.length ? `${overridden.length}` : "none"}
        />
      </dl>

      {overridden.length ? (
        <ul className="flex flex-wrap gap-1.5">
          {overridden.map(([key, value]) => (
            <li
              key={key}
              className="rounded-full border px-2.5 py-0.5 text-xs text-muted-foreground"
            >
              {key.startsWith(CONSTRAINT_PREFIX) ? key.slice(CONSTRAINT_PREFIX.length) : key} ={" "}
              {value}
            </li>
          ))}
        </ul>
      ) : null}

      {plan.unit.how ? (
        <WrappedField
          label={plan.unit.how}
          hint="Distinct designs, not the same one shifted along."
        >
          <Input
            type="number"
            min={1}
            max={20}
            value={text(draft, "howMany")}
            onChange={(event) => set("howMany", event.target.value)}
            placeholder="5"
            className="sm:max-w-[8rem]"
          />
        </WrappedField>
      ) : null}

      <div className="space-y-1.5 border-t pt-3">
        <Label htmlFor="label" className="text-sm font-medium">
          Name this attempt
        </Label>
        <Input
          id="label"
          value={text(draft, "label")}
          onChange={(event) => set("label", event.target.value)}
          placeholder="first pass, magnesium raised, …"
          className="sm:max-w-sm"
        />
        <p className="text-xs text-muted-foreground">
          Optional. It is how you will tell this run from the next one when you come back.
        </p>
      </div>

      {runnable ? (
        <div>
          <Button type="submit" disabled={pending || !ready}>
            {pending ? <Loader2 className="animate-spin" /> : <FlaskConical />}
            {pending ? "Designing…" : "Run and save"}
          </Button>
          {/*
           * The wait, said out loud. A disabled button is indistinguishable
           * from a stuck one after ten seconds, and these runs take up to
           * half a minute.
           */}
          {pending ? (
            <RunProgress
              job={job}
              starting={startingRun}
              cancelling={cancellingRun}
              onCancel={job && activeJob ? cancelCurrentRun : undefined}
            />
          ) : null}
          {!pending && missingRequirements.length ? (
            <p className="mt-2 max-w-prose text-xs leading-relaxed text-muted-foreground">
              Before running, provide the required{" "}
              {missingRequirements
                .map(
                  (requirement) =>
                    REQUIREMENT_LABELS[requirement] ?? readableFieldName(requirement),
                )
                .join(", ")}
              .
            </p>
          ) : null}
        </div>
      ) : (
        <div className="space-y-2">
          <Button type="button" disabled>
            <Hammer />
            Cannot run yet
          </Button>
          <p className="max-w-prose text-xs leading-relaxed text-muted-foreground">
            The engine behind this module is named but not written. Everything above is kept, so
            this project is ready the day it is — and until then the core answers a refusal rather
            than a result, which is why there is no button to press.
          </p>
        </div>
      )}
    </Step>
  );
}

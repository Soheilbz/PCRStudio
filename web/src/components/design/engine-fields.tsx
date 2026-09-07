"use client";

/**
 * The questions some engines ask that the others do not.
 *
 * Most assays want one target region and one set of constraints, and the
 * ordinary steps cover them. Several do not, and none of the differences is a
 * preference that could be defaulted away — each is a fact about the
 * experiment that nothing in a pasted sequence could supply.
 *
 * Inverse PCR needs to know where the enzyme cut. Nothing in a pasted sequence
 * says which enzyme somebody used, and the cut decides where the molecule
 * opens — so a design without one is not underspecified, it is undefined. It
 * also produces *two* circles, one walking each way, and which of them is
 * wanted is a fact about the experiment rather than about the sequence.
 *
 * Nested PCR designs two rounds, so one set of constraints cannot describe
 * both: the outer product is what a gel shows from round one and the inner is
 * what people actually read. And a single-tube nest is close to a second assay
 * — it is defined by a temperature gap between the rounds, and it needs an
 * enzyme without the activity that would destroy its own inner primers.
 *
 * Site-directed mutagenesis is told what to change rather than where to
 * amplify, and there is no default change: an edit quietly moved somewhere more
 * convenient is the wrong molecule.
 *
 * A single primer reads into its target rather than across it, so which way it
 * reads decides where it can sit at all — and the two figures describing the
 * read are a property of somebody's sequencing provider rather than of their
 * sequence.
 *
 * A tiling scheme covers everything, so it takes no target. What it takes
 * instead is how much neighbours must share and how many tubes to split across,
 * both of which are facts about the run rather than about the genome.
 */

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { EngineId } from "@/lib/api/types";
import type { ReactNode } from "react";
import { LampReactionFields, LampTargetFields, LoopFields } from "./engine-fields/lamp-fields";
import {
  FlankingNumericRecipeFields,
  SearchableFlankingProtocolSelect,
} from "./engine-fields/flanking-fields";
import { DigitalFragmentationFields, DigitalPcrFields } from "./engine-fields/digital-pcr-fields";
import {
  RACE_AUTHORITY,
  SEQUENCING_AUTHORITY,
  TILING_AUTHORITY,
} from "@/lib/engine-authorities.generated";
import { ProbeFields } from "./probe-fields";
import { EngineClosureFields } from "./engine-closure-fields";
import { EvidenceInput } from "./evidence-input";
import type { EngineFieldSection } from "./engine-field-types";
import { AssemblyFields, VariantFields } from "./engine-fields/advanced-fields";
export function asksSomethingExtra(engine: EngineId, moduleId?: string): boolean {
  return ENGINE_FIELD_RULES.some(
    (rule) => rule.section === "target" && matchesEngineFieldRule(rule, engine, moduleId),
  );
}

type EngineFieldRendererProps = {
  engine: EngineId;
  moduleId?: string;
  section: EngineFieldSection;
  value: (key: string) => string;
  onChange: (key: string, next: string) => void;
};

type EngineFieldRule = {
  engine: EngineId;
  section: EngineFieldSection;
  modules?: readonly string[];
  render: (props: EngineFieldRendererProps) => ReactNode;
};

function matchesEngineFieldRule(
  rule: EngineFieldRule,
  engine: EngineId,
  moduleId?: string,
): boolean {
  return (
    rule.engine === engine &&
    (rule.modules === undefined || (moduleId !== undefined && rule.modules.includes(moduleId)))
  );
}

export function EngineFields({
  engine,
  moduleId,
  section = "target",
  value,
  onChange,
}: {
  engine: EngineId;
  moduleId?: string;
  section?: EngineFieldSection;
  value: (key: string) => string;
  onChange: (key: string, next: string) => void;
}) {
  // Ownership is data, not a branching component: one table declares which
  // section owns every engine/module-specific control. Adding a field family
  // therefore cannot accidentally duplicate it across Target/Design/Strategy/
  // Reaction by adding another independent `if` chain.
  const rule = ENGINE_FIELD_RULES.find(
    (candidate) =>
      candidate.section === section && matchesEngineFieldRule(candidate, engine, moduleId),
  );
  return rule?.render({ engine, moduleId, section, value, onChange }) ?? null;
}

function RestrictionCloningWorkflowFields({
  value,
  onChange,
}: {
  value: (key: string) => string;
  onChange: (key: string, next: string) => void;
}) {
  return (
    <div className="space-y-4 rounded-lg border border-border/60 bg-surface-wash/25 p-4">
      <div>
        <h3 className="font-serif text-base font-semibold">
          Digest → dephosphorylation → ligation authority
        </h3>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          Primer-tail geometry and bench chemistry are separate contracts. Choose exact reviewed
          workflow families here; enzyme-specific temperature, methylation, heat-inactivation and
          double-digest facts remain unresolved until the exact enzyme catalogue supplies them.
        </p>
      </div>
      <div className="grid gap-3 lg:grid-cols-3">
        <div>
          <Label htmlFor="restrictionDigestProtocol" className="text-xs">
            Digest workflow
          </Label>
          <select
            id="restrictionDigestProtocol"
            required
            value={value("restrictionDigestProtocol")}
            onChange={(e) => onChange("restrictionDigestProtocol", e.target.value)}
            className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
          >
            <option value="">Choose digest authority</option>
            <option value="neb-cutsmart-standard">NEB rCutSmart · standard digest</option>
            <option value="neb-cutsmart-timesaver">NEB rCutSmart · Time-Saver branch</option>
            <option value="thermo-fastdigest-universal">
              Thermo Scientific · FastDigest universal
            </option>
          </select>
        </div>
        <div>
          <Label htmlFor="restrictionDephosphorylationProtocol" className="text-xs">
            Vector dephosphorylation
          </Label>
          <select
            id="restrictionDephosphorylationProtocol"
            required
            value={value("restrictionDephosphorylationProtocol")}
            onChange={(e) => onChange("restrictionDephosphorylationProtocol", e.target.value)}
            className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
          >
            <option value="">Record the step explicitly</option>
            <option value="none">None</option>
            <option value="neb-quick-cip-m0525">NEB Quick CIP · M0525</option>
          </select>
        </div>
        <div>
          <Label htmlFor="restrictionLigationProtocol" className="text-xs">
            Ligation workflow
          </Label>
          <select
            id="restrictionLigationProtocol"
            required
            value={value("restrictionLigationProtocol")}
            onChange={(e) => onChange("restrictionLigationProtocol", e.target.value)}
            className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
          >
            <option value="">Choose ligation authority</option>
            <option value="neb-t4-dna-ligase-m0202">NEB T4 DNA Ligase · M0202</option>
            <option value="neb-quick-ligation-m2200">NEB Quick Ligation · M2200</option>
          </select>
        </div>
      </div>
      <p className="text-xs leading-relaxed text-muted-foreground">
        The result records source-conditioned starting quantities and unresolved exact-enzyme
        dependencies. A 1:3 vector:insert ratio is preserved only as a source example/starting
        point, never promoted to a universal optimum.
      </p>
    </div>
  );
}

function ConsensusFields({
  value,
  onChange,
}: {
  value: (key: string) => string;
  onChange: (key: string, next: string) => void;
}) {
  const policy = value("consensusPolicy") || "strict-all-members";
  const formulation = value("formulationMode") || "mixed-base-synthesis";
  return (
    <div className="space-y-4 rounded-lg border border-border/60 bg-surface-wash/25 p-4">
      <div className="space-y-1">
        <h3 className="font-serif text-base font-semibold">
          Universal-primer panel & alignment authority
        </h3>
        <p className="text-xs leading-relaxed text-muted-foreground">
          Alignment, sampling frame, consensus policy and physical oligo formulation are explicit
          scientific inputs. Supplied weights are panel weights only; PCRStudio never re-labels them
          as population prevalence.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="alignmentMode" className="text-xs">
            Primary alignment
          </Label>
          <select
            id="alignmentMode"
            required
            value={value("alignmentMode")}
            onChange={(e) => onChange("alignmentMode", e.target.value)}
            className="h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
          >
            <option value="">Choose alignment authority</option>
            <option value="auto">MAFFT-first auto alignment — pinned backend</option>
            <option value="prealigned">Caller-supplied reviewed alignment</option>
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="consensusPolicy" className="text-xs">
            Consensus policy
          </Label>
          <select
            id="consensusPolicy"
            required
            value={policy}
            onChange={(e) => onChange("consensusPolicy", e.target.value)}
            className="h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
          >
            <option value="strict-all-members">
              Strict — retain every observed compatible base
            </option>
            <option value="coverage-threshold">Coverage threshold — record-count based</option>
            <option value="majority">Majority — 50% column support</option>
            <option value="weighted">Weighted supplied panel</option>
            <option value="stratified">Stratified — protect every declared stratum</option>
          </select>
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="panelMetadata" className="text-xs">
          Panel metadata / sampling frame (JSON)
        </Label>
        <textarea
          id="panelMetadata"
          value={value("panelMetadata")}
          onChange={(e) => onChange("panelMetadata", e.target.value)}
          rows={4}
          spellCheck={false}
          placeholder={'{"seq1":{"species":"A","stratum":"lineage-1","weight":1.0}}'}
          className="w-full rounded-lg border-border/70 bg-surface-wash/35 p-2 font-mono text-xs"
        />
        <p className="text-xs text-muted-foreground">
          Required for stratified policy. Metadata is reported and audited; records are never
          silently excluded.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="formulationMode" className="text-xs">
            Degenerate-oligo formulation
          </Label>
          <select
            id="formulationMode"
            required
            value={formulation}
            onChange={(e) => onChange("formulationMode", e.target.value)}
            className="h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
          >
            <option value="mixed-base-synthesis">Mixed-base synthesis</option>
            <option value="defined-oligo-pool">Defined oligo pool</option>
            <option value="discrete-subprimer-mixture">Discrete sub-primer mixture</option>
            <option value="user-defined-formulation">User-defined formulation</option>
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="formulationTotalConcentrationNm" className="text-xs">
            Declared total pool concentration (nM, optional)
          </Label>
          <Input
            id="formulationTotalConcentrationNm"
            type="number"
            min={0}
            step="any"
            value={value("formulationTotalConcentrationNm")}
            onChange={(e) => onChange("formulationTotalConcentrationNm", e.target.value)}
            placeholder="e.g. 500"
          />
        </div>
      </div>
      <details className="rounded-lg border border-border/60 bg-background/35 p-3">
        <summary className="cursor-pointer text-xs font-medium">
          Target/non-target and alignment-sensitivity evidence
        </summary>
        <div className="mt-3 space-y-3">
          <div>
            <Label htmlFor="nontarget" className="text-xs">
              Finite non-target FASTA panel
            </Label>
            <textarea
              id="nontarget"
              value={value("nontarget")}
              onChange={(e) => onChange("nontarget", e.target.value)}
              rows={4}
              spellCheck={false}
              className="mt-1 w-full rounded-lg border-border/70 bg-surface-wash/35 p-2 font-mono text-xs"
              placeholder={">near-neighbour\nACGT..."}
            />
          </div>
          <div>
            <Label htmlFor="alternativeAlignment" className="text-xs">
              Alternative reviewed alignment
            </Label>
            <textarea
              id="alternativeAlignment"
              value={value("alternativeAlignment")}
              onChange={(e) => onChange("alternativeAlignment", e.target.value)}
              rows={4}
              spellCheck={false}
              className="mt-1 w-full rounded-lg border-border/70 bg-surface-wash/35 p-2 font-mono text-xs"
              placeholder={">seq1\nACGT..."}
            />
          </div>
          <div>
            <Label htmlFor="alignmentAuditBackend" className="text-xs">
              Alternative alignment/backend identity
            </Label>
            <Input
              id="alignmentAuditBackend"
              value={value("alignmentAuditBackend")}
              onChange={(e) => onChange("alignmentAuditBackend", e.target.value)}
              placeholder="MUSCLE 5.3 / reviewed external MSA"
              className="mt-1"
            />
          </div>
        </div>
      </details>
      <p className="text-xs leading-relaxed text-muted-foreground">
        Non-target scans are bounded to the supplied records. Alternative alignments are sensitivity
        evidence and never silently replace the primary ranking.
      </p>
    </div>
  );
}

function ConsensusReactionFields({
  value,
  onChange,
}: {
  value: (key: string) => string;
  onChange: (key: string, next: string) => void;
}) {
  return (
    <div className="space-y-3 rounded-lg border border-border/60 bg-surface-wash/25 p-4">
      <div>
        <h3 className="font-serif text-base font-semibold">
          Universal-primer empirical validation
        </h3>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          Record what was observed for the selected formulation/panel. These fields are validation
          evidence only and do not retroactively change alignment coverage or candidate ranking.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <EvidenceInput
          id="universalScreenSetCount"
          label="Primer sets screened"
          type="number"
          value={value}
          onChange={onChange}
        />
        <EvidenceInput
          id="universalReplicates"
          label="Replicates"
          type="number"
          value={value}
          onChange={onChange}
        />
        <EvidenceInput
          id="universalNtcStatus"
          label="NTC status"
          value={value}
          onChange={onChange}
        />
        <EvidenceInput
          id="universalPositiveControlStatus"
          label="Positive-control status"
          value={value}
          onChange={onChange}
        />
        <EvidenceInput
          id="universalObservedCoverage"
          label="Observed target coverage"
          value={value}
          onChange={onChange}
        />
        <EvidenceInput
          id="universalInclusivityEvidence"
          label="Inclusivity evidence"
          value={value}
          onChange={onChange}
        />
        <EvidenceInput
          id="universalExclusivityEvidence"
          label="Exclusivity evidence"
          value={value}
          onChange={onChange}
        />
        <EvidenceInput
          id="universalFormulationEvidence"
          label="Actual formulation / synthesis evidence"
          value={value}
          onChange={onChange}
        />
        <EvidenceInput
          id="universalRawDataReference"
          label="Raw-data reference"
          value={value}
          onChange={onChange}
        />
        <EvidenceInput
          id="universalValidationNotes"
          label="Validation notes"
          value={value}
          onChange={onChange}
        />
      </div>
    </div>
  );
}

function StandardPcrFields({
  value,
  onChange,
}: {
  value: (key: string) => string;
  onChange: (key: string, next: string) => void;
}) {
  return (
    <div className="space-y-3 rounded-lg border border-border/60 bg-surface-wash/25 p-3">
      <div className="space-y-1">
        <h3 className="font-serif text-base font-semibold">Named Standard-PCR chemistry</h3>
        <p className="text-xs leading-relaxed text-muted-foreground">
          Optional bench/provenance overlay. Primer ranking stays on PCRStudio&apos;s versioned
          Standard-PCR screening context; selecting a vendor polymerase does not reconstruct a
          proprietary buffer or silently move primer Tm. Use the branch only when it matches the
          actual enzyme/master-mix used at the bench.
        </p>
      </div>
      <SearchableFlankingProtocolSelect
        id="standardPcrProtocol"
        moduleId="standard-pcr"
        value={value("standardPcrProtocol")}
        onChange={(next) => onChange("standardPcrProtocol", next)}
        disabledProtocols={new Set(["neb-multiplex-pcr-m0284"])}
      />
      <p className="text-xs leading-relaxed text-muted-foreground">
        The overlay records protocol-specific fidelity/hot-start state, dUTP/uracil compatibility,
        blunt versus 3′-dA product ends and difficult-template guidance. GC enhancer, DMSO, betaine
        or UDG are never auto-selected from sequence composition alone.
      </p>
      <FlankingNumericRecipeFields
        moduleId="standard-pcr"
        protocol={value("standardPcrProtocol")}
        value={value}
        onChange={onChange}
      />
    </div>
  );
}

function ColonyHostFields({
  value,
  onChange,
}: {
  value: (key: string) => string;
  onChange: (key: string, next: string) => void;
}) {
  return (
    <div className="space-y-3 rounded-lg border border-border/60 bg-surface-wash/25 p-3">
      <div className="space-y-1">
        <h3 className="font-serif text-base font-semibold">Colony biological context</h3>
        <p className="text-xs leading-relaxed text-muted-foreground">
          Host class belongs to the biological sample. The lysis/direct-transfer method and SOP
          belong to Reaction, where the bench preparation is recorded.
        </p>
      </div>
      <div>
        <Label htmlFor="colonyHostClass" className="text-xs">
          Host class
        </Label>
        <select
          id="colonyHostClass"
          required
          value={value("colonyHostClass")}
          onChange={(event) => onChange("colonyHostClass", event.target.value)}
          className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none sm:max-w-sm"
        >
          <option value="">Choose host class</option>
          <option value="bacterial">Bacterial</option>
          <option value="yeast">Yeast</option>
          <option value="filamentous-fungus">Filamentous fungus</option>
          <option value="microalgae">Microalgae</option>
          <option value="other">Other / validated SOP</option>
        </select>
      </div>
    </div>
  );
}

function ColonyPcrFields({
  value,
  onChange,
}: {
  value: (key: string) => string;
  onChange: (key: string, next: string) => void;
}) {
  const protocolId = value("colonyProtocolId") || "";
  const custom = protocolId === "custom-sop";
  const vendorProtocol = protocolId && !custom ? protocolId : "not-selected";
  const preparation = value("colonyPreparation");
  const sourceCompatibilityNote =
    protocolId === "pcrbio-hs-taq-pb10-22-colony"
      ? "Source-backed bacterial branches: direct colony transfer or liquid overnight culture. The public PB10.22 protocol uses a 50 µL reaction and distinguishes these two preparations."
      : protocolId.startsWith("neb-")
        ? "This reviewed NEB branch is source-backed for bacterial direct-colony transfer. Use Custom SOP for lysates, yeast/fungal hosts or another preparation."
        : custom
          ? "Custom SOP keeps host, preparation, identity and revision explicit; PCRStudio does not manufacture a lysis/cycling recipe from the host name."
          : "Select the exact bench workflow. Vendor protocols are restricted to the host/preparation scope documented by their source.";

  return (
    <div className="space-y-3 rounded-lg border border-border/60 bg-surface-wash/25 p-3">
      <div className="space-y-1">
        <h3 className="font-serif text-base font-semibold">Colony preparation / SOP authority</h3>
        <p className="text-xs leading-relaxed text-muted-foreground">
          Colony PCR is pre-analytically host- and workflow-dependent. Pick an exact reviewed vendor
          branch or declare a custom laboratory SOP. Vendor timing is never generalized to another
          host or preparation.
        </p>
      </div>
      <div>
        <Label htmlFor="colonyProtocolId" className="text-xs">
          Colony-PCR workflow
        </Label>
        <SearchableFlankingProtocolSelect
          id="colonyProtocolId"
          moduleId="colony-pcr"
          required
          allowNotSelected={false}
          value={protocolId}
          onChange={(next) => {
            onChange("colonyProtocolId", next);
            if (next !== "custom-sop") {
              onChange("colonyProtocolName", "");
              onChange("colonyProtocolProvenance", "");
            }
          }}
        />
        <button
          type="button"
          onClick={() => onChange("colonyProtocolId", "custom-sop")}
          className="mt-2 rounded-md border border-border/70 bg-background px-2 py-1 text-xs"
        >
          Use a custom / laboratory SOP
        </button>
      </div>
      <div>
        <Label htmlFor="colonyPreparation" className="text-xs">
          Template preparation
        </Label>
        <select
          id="colonyPreparation"
          required
          value={preparation}
          onChange={(event) => onChange("colonyPreparation", event.target.value)}
          className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          <option value="">Choose preparation</option>
          <option value="direct-transfer">Direct colony transfer</option>
          <option value="liquid-culture">Liquid / overnight culture</option>
          <option value="water-lysate">Water lysate</option>
          <option value="buffer-lysate">Buffer / TE lysate</option>
          <option value="host-specific-lysis">Host-specific lysis</option>
          <option value="other">Other validated preparation</option>
        </select>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          {sourceCompatibilityNote}
        </p>
      </div>
      <div>
        <Label htmlFor="colonySampleInputUl" className="text-xs">
          Liquid/lysate sample input (µL, when applicable)
        </Label>
        <Input
          id="colonySampleInputUl"
          inputMode="decimal"
          value={value("colonySampleInputUl")}
          onChange={(event) => onChange("colonySampleInputUl", event.target.value)}
          placeholder={
            preparation === "liquid-culture"
              ? "Record actual culture input"
              : "Optional measured input"
          }
          className="mt-1 sm:max-w-sm"
        />
        <p className="mt-1 text-xs text-muted-foreground">
          Leave blank for direct-colony transfer. PCRStudio records measured material rather than
          converting an isolated colony into an invented liquid volume.
        </p>
      </div>
      {custom ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <Label htmlFor="colonyProtocolName" className="text-xs">
              Laboratory SOP identity
            </Label>
            <Input
              id="colonyProtocolName"
              required
              value={value("colonyProtocolName")}
              onChange={(event) => onChange("colonyProtocolName", event.target.value)}
              placeholder="e.g. lab-colony-PCR-SOP-07 rev 3"
              className="mt-1"
            />
          </div>
          <div>
            <Label htmlFor="colonyProtocolProvenance" className="text-xs">
              SOP source / revision provenance
            </Label>
            <Input
              id="colonyProtocolProvenance"
              required
              value={value("colonyProtocolProvenance")}
              onChange={(event) => onChange("colonyProtocolProvenance", event.target.value)}
              placeholder="owner / revision / effective date / source"
              className="mt-1"
            />
          </div>
        </div>
      ) : null}
      {vendorProtocol !== "not-selected" ? (
        <FlankingNumericRecipeFields
          moduleId="colony-pcr"
          protocol={vendorProtocol}
          value={value}
          onChange={onChange}
        />
      ) : null}
    </div>
  );
}

function LongRangePcrFields({
  value,
  onChange,
}: {
  value: (key: string) => string;
  onChange: (key: string, next: string) => void;
}) {
  return (
    <div className="space-y-3 rounded-lg border border-border/60 bg-surface-wash/25 p-3">
      <div className="space-y-1">
        <h3 className="font-serif text-base font-semibold">
          Long-range chemistry / cycling authority
        </h3>
        <p className="text-xs leading-relaxed text-muted-foreground">
          Long-range PCR is protocol-coupled. Generation 1 does not manufacture a generic
          seconds-per-kilobase programme from product length. Select the named branch that actually
          owns the bench cycling model; otherwise strict design is refused.
        </p>
      </div>
      <div>
        <Label htmlFor="longRangeProtocol" className="text-xs">
          Named long-range protocol
        </Label>
        <SearchableFlankingProtocolSelect
          id="longRangeProtocol"
          moduleId="long-range-pcr"
          required
          allowNotSelected={false}
          value={value("longRangeProtocol")}
          onChange={(next) => onChange("longRangeProtocol", next)}
        />
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          Current NEB LongAmp, NEB Q5-XT, Takara PrimeSTAR GXL, QIAGEN UltraRun, TOYOBO KOD Long and
          Promega GoTaq Long branches are available alongside the historical K0181/K0182 record. The
          selected manufacturer protocol is carried into provenance; the shared thermodynamic screen
          remains a calculation adapter and never silently turns Primer3 Tm into a vendor bench
          annealing temperature.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <Label htmlFor="flankingTemplateClass" className="text-xs">
            Template class
          </Label>
          <select
            id="flankingTemplateClass"
            value={value("flankingTemplateClass")}
            onChange={(e) => onChange("flankingTemplateClass", e.target.value)}
            className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
          >
            <option value="">Choose template class</option>
            <option value="genomic">Genomic DNA</option>
            <option value="hmw-genomic">High-molecular-weight genomic DNA</option>
            <option value="plasmid">Plasmid / cloned insert</option>
            <option value="lambda">Lambda / simple DNA</option>
            <option value="lower-complexity">Other lower-complexity template</option>
            <option value="cDNA">cDNA</option>
            <option value="other">Other validated template</option>
          </select>
        </div>
        <label className="mt-6 flex items-start gap-2 text-xs text-muted-foreground">
          <input
            type="checkbox"
            checked={value("longRangeHmwTemplateVerified") === "true"}
            onChange={(e) =>
              onChange("longRangeHmwTemplateVerified", e.target.checked ? "true" : "false")
            }
          />
          <span>
            Intact high-molecular-weight template verified. For very long targets, template
            integrity is a qualification input, not something PCRStudio infers from sequence text.
          </span>
        </label>
      </div>
      <FlankingNumericRecipeFields
        moduleId="long-range-pcr"
        protocol={value("longRangeProtocol")}
        value={value}
        onChange={onChange}
      />
    </div>
  );
}

function QpcrSybrFields({
  value,
  onChange,
}: {
  value: (key: string) => string;
  onChange: (key: string, next: string) => void;
}) {
  return (
    <div className="space-y-3 rounded-lg border border-border/60 bg-surface-wash/25 p-3">
      <div className="space-y-1">
        <h3 className="font-serif text-base font-semibold">Named dye-qPCR chemistry</h3>
        <p className="text-xs leading-relaxed text-muted-foreground">
          Choose a named master-mix starting point only when its instrument and current guide match
          the bench. The overlay records kit/cycling/readout provenance and any vendor-preferred
          window without silently changing primer ranking; it cannot measure efficiency or prove a
          single product.
        </p>
      </div>
      <SearchableFlankingProtocolSelect
        id="qpcrProtocol"
        moduleId="qpcr-sybr"
        value={value("qpcrProtocol")}
        onChange={(next) => onChange("qpcrProtocol", next)}
        disabledProtocols={
          value("fromRna") === "true"
            ? new Set<string>()
            : new Set(["neb-luna-one-step-rt-qpcr-e3005", "promega-gotaq-one-step-rt-qpcr-a6020"])
        }
      />
      <p className="text-xs leading-relaxed text-muted-foreground">
        E3005 and A6020 are explicit one-step RNA branches and stay unavailable until RNA / one-step
        RT is declared on Target. qPCR-only mixes keep reverse transcription as a separate
        unresolved handoff rather than silently borrowing a named one-step RT recipe. PowerTrack is
        modelled as its own current product branch with source-conditioned fast/standard cycling.
      </p>
      <div>
        <Label htmlFor="qpcrInstrumentProfile" className="text-xs">
          Instrument / passive-reference profile
        </Label>
        <select
          id="qpcrInstrumentProfile"
          value={value("qpcrInstrumentProfile")}
          onChange={(e) => onChange("qpcrInstrumentProfile", e.target.value)}
          className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm sm:max-w-xl"
        >
          <option value="">Choose profile when chemistry depends on ROX/reference dye</option>
          <option value="high-rox">High ROX</option>
          <option value="low-rox">Low ROX</option>
          <option value="rox-compatible">ROX-compatible / exact instrument SOP</option>
          <option value="no-rox">No ROX</option>
          <option value="capillary">Capillary LightCycler-type profile</option>
          <option value="unresolved">
            Unresolved — retain as blocker where product requires it
          </option>
        </select>
        <p className="mt-1 text-xs text-muted-foreground">
          The instrument profile validates formulation compatibility; it does not change primer
          ranking.
        </p>
      </div>
      <FlankingNumericRecipeFields
        moduleId="qpcr-sybr"
        protocol={value("qpcrProtocol")}
        value={value}
        onChange={onChange}
      />
    </div>
  );
}

function RpaFields({
  value,
  onChange,
}: {
  value: (key: string) => string;
  onChange: (key: string, next: string) => void;
}) {
  return (
    <div className="space-y-3 rounded-lg border border-border/60 bg-surface-wash/25 p-3">
      <div className="space-y-1">
        <h3 className="font-serif text-base font-semibold">Named RPA chemistry</h3>
        <p className="text-xs leading-relaxed text-muted-foreground">
          Generation 1 executes named TwistAmp Basic/Liquid Basic DNA branches, the Thermo Fisher
          Lyo-ready RPA/RT-RPA branch and the G-Biosciences RPA kit. RPA does not use PCR melting
          temperature as a performance proof; candidate combinations still require an experimental
          primer screen. RNA is executable only when the selected named branch explicitly owns its
          reverse-transcriptase recipe.
        </p>
      </div>
      <SearchableFlankingProtocolSelect
        id="rpaProtocol"
        moduleId="rpa"
        required
        allowNotSelected={false}
        value={value("rpaProtocol")}
        onChange={(next) => onChange("rpaProtocol", next)}
      />
      <p className="text-xs leading-relaxed text-muted-foreground">
        Specialised Exo/Nfo/Fpg/SIBA branches are recognised rather than silently treated as Basic.
        They remain disabled until their internal modification, label/block and nuclease/readout
        topology can be represented without turning a modified probe into a false plain-DNA order.
      </p>
      <FlankingNumericRecipeFields
        moduleId="rpa"
        protocol={value("rpaProtocol")}
        value={value}
        onChange={onChange}
      />
    </div>
  );
}

/**
 * The probe's own window, which is not the primers'.
 *
 * The engine has taken a probe block since it was written and no page filled
 * it in, so a probe assay was always designed on the derived window — the
 * primers' plus seven degrees — and somebody using a chemistry with a
 * different requirement had nowhere to say so. A minor-groove binder melts
 * around ten degrees above the same sequence unmodified and is deliberately
 * short; a locked-nucleic-acid probe is shorter still. Both are ordinary and
 * neither fits a window derived from the primers.
 *
 * Empty means derived, which is why every box here is empty rather than
 * pre-filled: a number shown in a box is a number somebody chose, and these
 * follow from the primers until they do not.
 */
/**
 * What to change, and where.
 *
 * Required, and there is nothing to default it to. Every other engine here is
 * given a region and asked to amplify across it; this one is given a change and
 * asked to make it, and a design that quietly put the change somewhere more
 * convenient would produce the wrong molecule.
 */
function EditFields({
  section,
  value,
  onChange,
}: {
  section: "design" | "reaction";
  value: (key: string) => string;
  onChange: (key: string, next: string) => void;
}) {
  const topology = value("mutagenesisTopology") || "q5-back-to-back";
  const inputMode = value("editInputMode") || "dna";

  if (section === "reaction") {
    const expectedProtocol =
      topology === "q5-back-to-back"
        ? "neb-q5-e0554"
        : topology === "quikchange-complementary"
          ? "agilent-quikchange-lightning-210518"
          : topology === "quikchange-lightning-multi"
            ? "agilent-quikchange-lightning-multi-210513-210516"
            : "neb-nebuilder-multisite";
    return (
      <div className="space-y-4 rounded-lg border border-border/60 bg-surface-wash/25 p-4">
        <div>
          <h3 className="font-serif text-base font-semibold">
            Topology-specific mutagenesis chemistry
          </h3>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            Q5, QuikChange single-site, Lightning Multi and NEBuilder multi-site are independent
            reaction topologies. PCRStudio never converts one into another merely because the edit
            sequence happens to fit.
          </p>
        </div>
        <div className="grid gap-3 lg:grid-cols-2">
          <div>
            <Label htmlFor="postAmplificationProtocol" className="text-xs">
              Reviewed workflow
            </Label>
            <select
              id="postAmplificationProtocol"
              required
              value={value("postAmplificationProtocol") || expectedProtocol}
              onChange={(e) => onChange("postAmplificationProtocol", e.target.value)}
              className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
            >
              <option value="neb-q5-e0554">NEB Q5 E0554 · back-to-back + KLD</option>
              <option value="agilent-quikchange-lightning-210518">
                Agilent QuikChange Lightning · single-site
              </option>
              <option value="agilent-quikchange-lightning-multi-210513-210516">
                Agilent QuikChange Lightning Multi
              </option>
              <option value="neb-nebuilder-multisite">
                PCRStudio multi-site NEBuilder routing (NEBaseChanger workflow reference)
              </option>
            </select>
            <p className="mt-1 text-xs text-muted-foreground">
              Expected for the selected topology: <code>{expectedProtocol}</code>. A mismatch is
              refused by the worker rather than silently reinterpreted.
            </p>
          </div>
          <div>
            <Label htmlFor="templateMethylationStatus" className="text-xs">
              Parental-template methylation
            </Label>
            <select
              id="templateMethylationStatus"
              value={value("templateMethylationStatus") || "unknown"}
              onChange={(e) => onChange("templateMethylationStatus", e.target.value)}
              className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
            >
              <option value="unknown">Unknown / not recorded</option>
              <option value="dam-methylated">Dam-methylated</option>
              <option value="unmethylated">Unmethylated</option>
              <option value="other-reviewed">Other reviewed state</option>
            </select>
          </div>
        </div>

        <details className="rounded-lg border border-border/60 bg-background/35 p-3">
          <summary className="cursor-pointer text-xs font-medium">
            Bench validation evidence
          </summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <EvidenceInput
              id="mutagenesisPcrEvidence"
              label="PCR evidence"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="mutagenesisDpnIKldEvidence"
              label="DpnI / KLD evidence"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="mutagenesisTransformationEvidence"
              label="Transformation evidence"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="mutagenesisColonyCount"
              label="Colony count"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="mutagenesisClonesScreened"
              label="Clones screened"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="mutagenesisVerifiedCloneCount"
              label="Verified clones"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="mutagenesisSequenceReference"
              label="Sanger/NGS reference"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="mutagenesisUnintendedMutationStatus"
              label="Unintended-mutation status"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="mutagenesisValidationNotes"
              label="Validation notes"
              value={value}
              onChange={onChange}
            />
          </div>
          <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
            These are empirical records only. They are persisted with the run and have no
            sequence-ranking impact.
          </p>
        </details>
      </div>
    );
  }

  const kind = value("editKind");
  return (
    <div className="space-y-4 rounded-lg border border-border/60 bg-surface-wash/25 p-4">
      <div>
        <h3 className="font-serif text-base font-semibold">Edit and mutagenesis topology</h3>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          Define the exact molecular change first, then select the topology that can make it. The
          predicted final construct remains separate from clone-level sequence verification.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <Label htmlFor="mutagenesisTopology" className="text-xs">
            Mutagenesis topology
          </Label>
          <select
            id="mutagenesisTopology"
            required
            value={topology}
            onChange={(e) => onChange("mutagenesisTopology", e.target.value)}
            className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
          >
            <option value="q5-back-to-back">Q5 · back-to-back / non-overlapping</option>
            <option value="quikchange-complementary">
              QuikChange Lightning · complementary pair
            </option>
            <option value="quikchange-lightning-multi">
              QuikChange Lightning Multi · one primer/site
            </option>
            <option value="nebuilder-multisite">
              NEBuilder multi-site · route through assembly
            </option>
          </select>
        </div>
        <div>
          <Label htmlFor="editInputMode" className="text-xs">
            Edit input
          </Label>
          <select
            id="editInputMode"
            value={inputMode}
            onChange={(e) => {
              const next = e.target.value;
              onChange("editInputMode", next);
              if (next === "library") {
                if (!value("libraryMode") || value("libraryMode") === "none") {
                  onChange("libraryMode", "NNK");
                }
              } else if (value("libraryMode") && value("libraryMode") !== "none") {
                // A hidden stale library selection must never turn a DNA, multi-edit,
                // or amino-acid request into a library request at transport time.
                onChange("libraryMode", "none");
              }
            }}
            className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
          >
            <option value="dna">Single DNA edit</option>
            <option value="multi">Multiple DNA edits</option>
            <option value="amino-acid">Protein residue edit</option>
            <option value="library">Degenerate codon library</option>
          </select>
        </div>
      </div>

      {inputMode === "dna" ? (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <Label htmlFor="editKind" className="text-xs">
                Kind
              </Label>
              <select
                id="editKind"
                required
                value={kind}
                onChange={(e) => onChange("editKind", e.target.value)}
                className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
              >
                <option value="">Choose edit kind</option>
                <option value="substitute">Substitute</option>
                <option value="insert">Insert</option>
                <option value="delete">Delete</option>
              </select>
            </div>
            <div>
              <Label htmlFor="editAt" className="text-xs">
                At base
              </Label>
              <Input
                id="editAt"
                inputMode="numeric"
                required
                value={value("editAt")}
                onChange={(e) => onChange("editAt", e.target.value)}
                placeholder="1-based"
                className="mt-1"
              />
            </div>
            <div>
              <Label htmlFor="editReplacing" className="text-xs">
                {kind === "insert" ? "Replacing (none)" : "Bases replaced"}
              </Label>
              <Input
                id="editReplacing"
                inputMode="numeric"
                required={kind === "substitute" || kind === "delete"}
                value={value("editReplacing")}
                onChange={(e) => onChange("editReplacing", e.target.value)}
                disabled={kind === "insert"}
                placeholder={kind === "insert" ? "0" : "1"}
                className="mt-1"
              />
            </div>
          </div>
          {kind === "delete" ? null : (
            <div>
              <Label htmlFor="editTo" className="text-xs">
                New sequence
              </Label>
              <Input
                id="editTo"
                required={kind === "substitute" || kind === "insert"}
                value={value("editTo")}
                onChange={(e) => onChange("editTo", e.target.value.toUpperCase())}
                placeholder="ACGT..."
                className="mt-1 font-mono"
              />
              <p className="mt-1 text-xs text-muted-foreground">
                Q5 insertions longer than 6 nt use reviewed split 5′ tails; 7–100 nt are represented
                explicitly rather than refused or collapsed into one tail.
              </p>
            </div>
          )}
        </>
      ) : null}

      {inputMode === "multi" ? (
        <div>
          <Label htmlFor="editsJson" className="text-xs">
            Edits (JSON, UI coordinates are 1-based)
          </Label>
          <textarea
            id="editsJson"
            value={value("editsJson")}
            onChange={(e) => onChange("editsJson", e.target.value)}
            rows={7}
            spellCheck={false}
            placeholder={
              '[\n  {"kind":"substitute","at":45,"to":"G","replacing":1},\n  {"kind":"delete","at":120,"replacing":3}\n]'
            }
            className="mt-1 w-full rounded-lg border-border/70 bg-surface-wash/35 p-2 font-mono text-xs"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Overlapping edits are refused; use one explicit complex edit when two edits overlap on
            the reference molecule.
          </p>
        </div>
      ) : null}

      {inputMode === "amino-acid" ? (
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-5">
            <EvidenceInput
              id="aaCdsStart"
              label="CDS start base"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="aaResidue"
              label="Residue"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="aaFrom"
              label="From AA (optional)"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput id="aaTo" label="To AA" value={value} onChange={onChange} />
            <EvidenceInput
              id="aaCodon"
              label="Chosen codon (optional)"
              value={value}
              onChange={onChange}
            />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <Label htmlFor="codonPolicy" className="text-xs">
                Codon policy
              </Label>
              <select
                id="codonPolicy"
                value={value("codonPolicy") || "minimum-nucleotide-changes"}
                onChange={(e) => onChange("codonPolicy", e.target.value)}
                className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
              >
                <option value="minimum-nucleotide-changes">Minimum nucleotide changes</option>
                <option value="user-selected-codon">User-selected codon</option>
                <option value="host-codon-usage">Caller-supplied host codon usage</option>
              </select>
            </div>
            {value("codonPolicy") === "host-codon-usage" ? (
              <div>
                <Label htmlFor="codonUsage" className="text-xs">
                  Codon usage JSON
                </Label>
                <textarea
                  id="codonUsage"
                  value={value("codonUsage")}
                  onChange={(e) => onChange("codonUsage", e.target.value)}
                  rows={4}
                  spellCheck={false}
                  placeholder={'{"GTT":0.18,"GTC":0.24,"GTA":0.12,"GTG":0.46}'}
                  className="mt-1 w-full rounded-lg border-border/70 bg-surface-wash/35 p-2 font-mono text-xs"
                />
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      {inputMode === "library" ? (
        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <Label htmlFor="libraryMode" className="text-xs">
              Library codon
            </Label>
            <select
              id="libraryMode"
              value={
                value("libraryMode") && value("libraryMode") !== "none"
                  ? value("libraryMode")
                  : "NNK"
              }
              onChange={(e) => onChange("libraryMode", e.target.value)}
              className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
            >
              <option value="NNK">NNK</option>
              <option value="NNS">NNS</option>
              <option value="custom">Custom IUPAC codon</option>
            </select>
          </div>
          <EvidenceInput
            id="libraryAt"
            label="Codon start base"
            type="number"
            value={value}
            onChange={onChange}
          />
          {value("libraryMode") === "custom" ? (
            <EvidenceInput
              id="libraryCodon"
              label="IUPAC codon"
              value={value}
              onChange={onChange}
            />
          ) : (
            <div />
          )}
          <p className="text-xs leading-relaxed text-muted-foreground sm:col-span-3">
            Theoretical library sequence space is reported separately from synthesis abundance and
            clone distribution; no equal-abundance claim is made.
          </p>
        </div>
      ) : null}
    </div>
  );
}

/**
 * Which way the primer reads, and how far the trace stays legible.
 *
 * The direction is the design: a target too close to one end of the template
 * can be unreachable one way and straightforward the other. The two read
 * figures describe somebody's sequencing provider rather than their sequence,
 * so they are left alone unless that provider quotes different ones.
 */
type AuthorityRecord = {
  kind?: string;
  selection?: string;
  execution_status?: string;
  note?: string;
  requires?: { sop_revision?: boolean; sop_sha256?: boolean };
};

function ReadFields({
  section,
  moduleId,
  value,
  onChange,
}: {
  section: "design" | "reaction";
  moduleId?: string;
  value: (key: string) => string;
  onChange: (key: string, next: string) => void;
}) {
  const raceRecords = (RACE_AUTHORITY as { records: Record<string, AuthorityRecord> }).records;
  const sequencingRecords = (SEQUENCING_AUTHORITY as { records: Record<string, AuthorityRecord> })
    .records;

  if (section === "design") {
    if (moduleId === "race") {
      return (
        <div className="space-y-3 rounded-lg border border-border/60 bg-surface-wash/25 p-4">
          <div>
            <h3 className="font-serif text-base font-semibold">
              RACE gene-specific primer geometry
            </h3>
            <p className="mt-1 text-xs text-muted-foreground">
              The transcript end determines strand direction. Kit-specific GSP Tm/length/GC rules
              are applied later from the selected RACE chemistry; they are not shared with Sanger
              design.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <Label htmlFor="raceDirection" className="text-xs">
                Transcript end
              </Label>
              <select
                id="raceDirection"
                required
                value={value("raceDirection")}
                onChange={(e) => onChange("raceDirection", e.target.value)}
                className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
              >
                <option value="">Choose end</option>
                <option value="5prime">5′ RACE</option>
                <option value="3prime">3′ RACE</option>
              </select>
            </div>
            <div>
              <Label htmlFor="raceRound" className="text-xs">
                GSP round
              </Label>
              <select
                id="raceRound"
                required
                value={value("raceRound")}
                onChange={(e) => onChange("raceRound", e.target.value)}
                className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
              >
                <option value="">Choose round</option>
                <option value="primary">Primary / outer GSP</option>
                <option value="nested">Nested / inner GSP</option>
              </select>
            </div>
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground">
            5′ RACE uses an antisense GSP; 3′ RACE uses a sense GSP. A band is reported only as a
            candidate transcript end until sequencing evidence confirms it.
          </p>
        </div>
      );
    }
    if (moduleId === "sequencing-primer") {
      const designProfile = value("sequencingDesignProfile") || "generic-cycle-sequencing";
      const profile = sequencingRecords[designProfile];
      return (
        <div className="space-y-3 rounded-lg border border-border/60 bg-surface-wash/25 p-4">
          <div>
            <h3 className="font-serif text-base font-semibold">
              Service-aware Sanger primer placement
            </h3>
            <p className="mt-1 text-xs text-muted-foreground">
              Design constraints come from the selected sequencing-service profile; submission
              concentrations stay separate on Reaction and never change candidate ranking.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <Label htmlFor="sequencingDesignProfile" className="text-xs">
                Design profile
              </Label>
              <select
                id="sequencingDesignProfile"
                required
                value={designProfile}
                onChange={(e) => {
                  onChange("sequencingDesignProfile", e.target.value);
                  onChange("sequencingProvider", e.target.value);
                }}
                className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
              >
                {Object.entries(sequencingRecords)
                  .filter(([, r]) => r.kind === "sequencing-design-profile")
                  .map(([id, r]) => (
                    <option key={id} value={id}>
                      {String(r.selection || id)}
                    </option>
                  ))}
              </select>
            </div>
            <div>
              <Label htmlFor="direction" className="text-xs">
                Read direction
              </Label>
              <select
                id="direction"
                required
                value={value("direction")}
                onChange={(e) => onChange("direction", e.target.value)}
                className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
              >
                <option value="">Choose direction</option>
                <option value="forward">Forward</option>
                <option value="reverse">Reverse</option>
              </select>
            </div>
            <div>
              <Label htmlFor="deadZone" className="text-xs">
                Unreadable start / provider value (bp)
              </Label>
              <Input
                id="deadZone"
                required
                type="number"
                min={0}
                value={value("deadZone")}
                onChange={(e) => onChange("deadZone", e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="readLength" className="text-xs">
                Usable read length / provider value (bp)
              </Label>
              <Input
                id="readLength"
                required
                type="number"
                min={1}
                value={value("readLength")}
                onChange={(e) => onChange("readLength", e.target.value)}
              />
            </div>
            <div className="flex items-end gap-2">
              <input
                id="sequencingUniversalPrimerScan"
                type="checkbox"
                checked={value("sequencingUniversalPrimerScan") !== "false"}
                onChange={(e) =>
                  onChange("sequencingUniversalPrimerScan", e.target.checked ? "true" : "false")
                }
              />
              <Label htmlFor="sequencingUniversalPrimerScan" className="text-xs">
                Check curated vector primers first
              </Label>
            </div>
            <div className="flex items-end gap-2">
              <input
                id="sequencingBidirectional"
                type="checkbox"
                checked={value("sequencingBidirectional") === "true"}
                onChange={(e) =>
                  onChange("sequencingBidirectional", e.target.checked ? "true" : "false")
                }
              />
              <Label htmlFor="sequencingBidirectional" className="text-xs">
                Plan bidirectional confirmation
              </Label>
            </div>
          </div>
          <div className="rounded-md border border-border/60 bg-background/35 p-2 text-xs text-muted-foreground">
            Selected profile: <strong>{String(profile?.selection || designProfile)}</strong>.
            Provider guidance is a named design envelope, not a universal Sanger law.
          </div>
        </div>
      );
    }
    return null;
  }

  if (moduleId === "sequencing-primer") {
    return (
      <div className="space-y-4 rounded-lg border border-border/60 bg-surface-wash/25 p-4">
        <div>
          <h3 className="font-serif text-base font-semibold">
            Cycle-sequencing handoff & trace evidence
          </h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Chemistry, instrument, sample-submission quantities and trace quality are bench/service
            metadata. They do not rewrite the provider-specific design envelope.
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <Label htmlFor="sequencingProtocol" className="text-xs">
              Cycle-sequencing chemistry
            </Label>
            <select
              id="sequencingProtocol"
              value={value("sequencingProtocol")}
              onChange={(e) => onChange("sequencingProtocol", e.target.value)}
              className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
            >
              <option value="">Not selected</option>
              <option value="bigdye-v3-1">Applied Biosystems BigDye Terminator v3.1</option>
            </select>
          </div>
          <EvidenceInput
            id="sequencingProvider"
            label="Provider / facility"
            value={value}
            onChange={onChange}
            placeholder="Azenta, Eurofins, institutional core…"
          />
          <div>
            <Label htmlFor="sequencingInstrument" className="text-xs">
              Capillary instrument
            </Label>
            <select
              id="sequencingInstrument"
              value={value("sequencingInstrument") || "unresolved"}
              onChange={(e) => onChange("sequencingInstrument", e.target.value)}
              className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
            >
              <option value="unresolved">Unresolved/provider decides</option>
              <option value="seqstudio">SeqStudio</option>
              <option value="seqstudio-flex">SeqStudio Flex</option>
              <option value="3500">3500</option>
              <option value="3500xl">3500xL</option>
              <option value="3730">3730</option>
              <option value="3730xl">3730xl</option>
              <option value="other">Other</option>
            </select>
          </div>
          {value("sequencingInstrument") === "other" ? (
            <EvidenceInput
              id="sequencingInstrumentName"
              label="Instrument name"
              value={value}
              onChange={onChange}
            />
          ) : null}
          <EvidenceInput
            id="sequencingFacilitySop"
            label="Facility / submission SOP"
            value={value}
            onChange={onChange}
            placeholder="SOP/revision; includes concentration/volume requirements"
          />
        </div>
        <details className="rounded-lg border border-border/60 bg-background/35 p-3">
          <summary className="cursor-pointer text-xs font-medium">Trace evidence</summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <EvidenceInput
              id="sequencingObservedReadLength"
              label="Observed usable read length"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="sequencingMeanQuality"
              label="Mean quality / Phred summary"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="sequencingTraceReference"
              label="AB1/SCF trace reference"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="sequencingMixedPeakStatus"
              label="Mixed-peak status"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="sequencingInstrumentEvidence"
              label="Run instrument/software"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput id="sequencingRunId" label="Run ID" value={value} onChange={onChange} />
            <EvidenceInput
              id="sequencingValidationNotes"
              label="Validation notes"
              value={value}
              onChange={onChange}
            />
          </div>
        </details>
      </div>
    );
  }

  if (moduleId === "race") {
    const chemistry = value("raceChemistry") || "generacer-kit-25-0355-vl";
    const selected = raceRecords[chemistry];
    return (
      <div className="space-y-4 rounded-lg border border-border/60 bg-surface-wash/25 p-4">
        <div>
          <h3 className="font-serif text-base font-semibold">RACE chemistry, partner & evidence</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            GeneRacer, RLM-RACE and SMARTer are distinct workflows. Exact adapter/GSP envelopes are
            used only when the selected authority is complete. SMARTer is executable only with
            complete supplied context; source-limited historical entries remain disabled.
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <Label htmlFor="raceChemistry" className="text-xs">
              RACE chemistry
            </Label>
            <select
              id="raceChemistry"
              required
              value={chemistry}
              onChange={(e) => {
                const next = e.target.value;
                onChange("raceChemistry", next);
                onChange(
                  "raceAdapter",
                  next === "generacer-kit-25-0355-vl" ||
                    next === "firstchoice-rlm-race" ||
                    next === "smarter-race-current"
                    ? next
                    : next === "custom"
                      ? "custom"
                      : "",
                );
              }}
              className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
            >
              {Object.entries(raceRecords)
                .filter(([, r]) => r.kind === "race-chemistry" || r.kind === "race-design-profile")
                .map(([id, r]) => (
                  <option
                    key={id}
                    value={id}
                    disabled={!String(r.execution_status || "").startsWith("executable")}
                  >
                    {String(r.selection || id)}
                    {!String(r.execution_status || "").startsWith("executable")
                      ? " · source-limited"
                      : ""}
                  </option>
                ))}
            </select>
          </div>
          <div>
            <Label htmlFor="raceSubstrate" className="text-xs">
              Biological substrate
            </Label>
            <select
              id="raceSubstrate"
              required
              value={value("raceSubstrate")}
              onChange={(e) => onChange("raceSubstrate", e.target.value)}
              className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
            >
              <option value="">Choose substrate</option>
              <option value="total-rna">Total RNA</option>
              <option value="mrna">mRNA/poly(A)-enriched</option>
              <option value="cdna">Prepared cDNA</option>
            </select>
          </div>
        </div>
        <EvidenceInput
          id="racePreparation"
          label="RNA/cDNA preparation provenance"
          value={value}
          onChange={onChange}
          placeholder="Kit/SOP, cap treatment, RT/template-switch/ligation preparation"
        />
        {chemistry === "custom" || chemistry === "smarter-race-current" ? (
          <EvidenceInput
            id="racePartnerSequence"
            label={
              chemistry === "smarter-race-current"
                ? "SMARTer exact universal PCR-partner sequence"
                : "Custom exact PCR-partner sequence"
            }
            value={value}
            onChange={onChange}
            placeholder="A/C/G/T sequence"
          />
        ) : null}
        {chemistry === "custom" || chemistry === "smarter-race-current" ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <EvidenceInput
              id="raceSopRevision"
              label="Reviewed SOP/manual revision"
              value={value}
              onChange={onChange}
              placeholder="Document/catalog/revision identity"
            />
            <EvidenceInput
              id="raceSopSha256"
              label="Reviewed SOP/manual SHA-256"
              value={value}
              onChange={onChange}
              placeholder="64 lowercase/uppercase hex characters"
            />
          </div>
        ) : null}
        <div className="rounded-md border border-border/60 bg-background/35 p-2 text-xs text-muted-foreground">
          {String(
            selected?.note ||
              "The selected chemistry owns its exact adapter/partner and GSP envelope.",
          )}
        </div>
        <details className="rounded-lg border border-border/60 bg-background/35 p-3">
          <summary className="cursor-pointer text-xs font-medium">RACE workflow evidence</summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <EvidenceInput
              id="raceObservedBandBp"
              label="Observed band (bp)"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="raceReplicates"
              label="Replicates"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput id="raceRnaQc" label="RNA QC" value={value} onChange={onChange} />
            <EvidenceInput
              id="raceDnaseEvidence"
              label="DNase evidence"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="raceRtEvidence"
              label="RT/cDNA evidence"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="raceOuterPcrEvidence"
              label="Outer PCR evidence"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="raceNestedPcrEvidence"
              label="Nested PCR evidence"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="raceCloneReference"
              label="Clone/product reference"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="raceSequenceConfirmation"
              label="Sequence confirmation"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="raceValidationNotes"
              label="Validation notes"
              value={value}
              onChange={onChange}
            />
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            A RACE band is a candidate end; confirmed transcript-end status requires sequence
            evidence.
          </p>
        </details>
      </div>
    );
  }
  return null;
}

/**
 * How much neighbours share, and how many tubes to split across.
 *
 * There is no target here — the whole sequence is the job — so what is asked
 * instead is the shape of the walk. Neighbouring amplicons overlap and so
 * cannot share a tube: in one reaction their primers would amplify each other's
 * short products in preference to the real ones.
 */
function SchemeFields({
  section,
  value,
  onChange,
}: {
  section: "strategy" | "design" | "reaction";
  value: (key: string) => string;
  onChange: (key: string, next: string) => void;
}) {
  const operation = value("tilingOperation") || "scheme-create";
  const backend = value("tilingBackend") || "primalscheme3";
  const primal = backend === "primalscheme3" || backend === "compare";
  const olivar = backend === "olivar" || backend === "compare";
  const tilingRecords = (TILING_AUTHORITY as { records: Record<string, AuthorityRecord> }).records;

  if (section === "design") {
    return (
      <div className="space-y-4 rounded-lg border border-border/60 bg-surface-wash/25 p-4">
        <div>
          <h3 className="font-serif text-base font-semibold">
            Backend-specific tiled-design parameters
          </h3>
          <p className="mt-1 text-xs text-muted-foreground">
            PrimalScheme and Olivar are independent engines. Their defaults and risk scores are
            never averaged or promoted to generic PCR rules.
          </p>
        </div>
        {primal && operation === "scheme-create" ? (
          <div className="space-y-3 rounded-lg border border-border/60 bg-background/35 p-3">
            <h4 className="text-sm font-semibold">PrimalScheme3 3.3.0</h4>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <Label htmlFor="overlap" className="text-xs">
                  Minimum overlap (bp)
                </Label>
                <Input
                  id="overlap"
                  required
                  type="number"
                  min={0}
                  value={value("overlap")}
                  onChange={(e) => onChange("overlap", e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="tilingMinBaseFrequency" className="text-xs">
                  Minimum base frequency
                </Label>
                <Input
                  id="tilingMinBaseFrequency"
                  type="number"
                  min={0}
                  max={1}
                  step="0.001"
                  value={value("tilingMinBaseFrequency")}
                  onChange={(e) => onChange("tilingMinBaseFrequency", e.target.value)}
                  placeholder="tool default: 0.0"
                />
              </div>
              <label className="flex items-end gap-2 pb-2 text-xs">
                <input
                  id="tilingBacktrack"
                  type="checkbox"
                  checked={value("tilingBacktrack") === "true"}
                  onChange={(e) => onChange("tilingBacktrack", e.target.checked ? "true" : "false")}
                />{" "}
                Backtrack to avoid gaps
              </label>
              <label className="flex items-end gap-2 pb-2 text-xs">
                <input
                  id="tilingHighGc"
                  type="checkbox"
                  checked={value("tilingHighGc") === "true"}
                  onChange={(e) => onChange("tilingHighGc", e.target.checked ? "true" : "false")}
                />{" "}
                High-GC primer profile
              </label>
            </div>
          </div>
        ) : null}
        {primal && operation === "panel-create" ? (
          <div className="space-y-3 rounded-lg border border-border/60 bg-background/35 p-3">
            <h4 className="text-sm font-semibold">PrimalScheme panel design</h4>
            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                <Label htmlFor="panelMode" className="text-xs">
                  Panel mode
                </Label>
                <select
                  id="panelMode"
                  required
                  value={value("panelMode")}
                  onChange={(e) => onChange("panelMode", e.target.value)}
                  className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
                >
                  <option value="">Choose</option>
                  <option value="region-only">Region-only</option>
                  <option value="entropy">Entropy-aware</option>
                  <option value="equal">Equal allocation</option>
                </select>
              </div>
              <div>
                <Label htmlFor="tilingMinBaseFrequency" className="text-xs">
                  Minimum base frequency
                </Label>
                <Input
                  id="tilingMinBaseFrequency"
                  type="number"
                  min={0}
                  max={1}
                  step="0.001"
                  value={value("tilingMinBaseFrequency")}
                  onChange={(e) => onChange("tilingMinBaseFrequency", e.target.value)}
                  placeholder="tool default: 0.0"
                />
              </div>
              <label className="flex items-end gap-2 pb-2 text-xs">
                <input
                  id="tilingHighGc"
                  type="checkbox"
                  checked={value("tilingHighGc") === "true"}
                  onChange={(e) => onChange("tilingHighGc", e.target.checked ? "true" : "false")}
                />{" "}
                High-GC primer profile
              </label>
            </div>
            <LifecycleText
              id="regionBed"
              label="Region BED — optional"
              value={value("regionBed")}
              onChange={onChange}
              placeholder="chrom<TAB>start<TAB>end<TAB>region"
            />
          </div>
        ) : null}
        {olivar ? (
          <div className="space-y-3 rounded-lg border border-border/60 bg-background/35 p-3">
            <h4 className="text-sm font-semibold">Olivar 1.3.3 · variant-aware backend</h4>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <Label htmlFor="olivarSeed" className="text-xs">
                  Deterministic seed
                </Label>
                <Input
                  id="olivarSeed"
                  type="number"
                  min={0}
                  value={value("olivarSeed") || "10"}
                  onChange={(e) => onChange("olivarSeed", e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="tilingMinBaseFrequency" className="text-xs">
                  Minimum variant frequency
                </Label>
                <Input
                  id="tilingMinBaseFrequency"
                  type="number"
                  min={0}
                  max={1}
                  step="0.001"
                  value={value("tilingMinBaseFrequency")}
                  onChange={(e) => onChange("tilingMinBaseFrequency", e.target.value)}
                  placeholder="0.01"
                />
              </div>
              <label className="flex items-end gap-2 pb-2 text-xs">
                <input
                  id="olivarDegenerateMode"
                  type="checkbox"
                  checked={value("olivarDegenerateMode") === "true"}
                  onChange={(e) =>
                    onChange("olivarDegenerateMode", e.target.checked ? "true" : "false")
                  }
                />{" "}
                Degenerate-base mode
              </label>
              <label className="flex items-end gap-2 pb-2 text-xs">
                <input
                  id="olivarCheckVariants"
                  type="checkbox"
                  checked={value("olivarCheckVariants") !== "false"}
                  onChange={(e) =>
                    onChange("olivarCheckVariants", e.target.checked ? "true" : "false")
                  }
                />{" "}
                Variant-aware tiling check
              </label>
            </div>
            <p className="text-xs leading-relaxed text-muted-foreground">
              Olivar is external-managed and must be provisioned as an explicit fingerprinted
              executable/wrapper. PCRStudio never guesses Linux/Conda paths. SADDLE/risk scores
              remain Olivar-specific evidence.
            </p>
          </div>
        ) : null}
        {operation === "repair-mode" || operation === "scheme-replace" ? (
          <p className="text-xs text-muted-foreground">
            Repair/replace inherits design geometry from the reviewed PrimalScheme BED/config and is
            intentionally unavailable to Olivar/compare.
          </p>
        ) : null}
      </div>
    );
  }

  if (section === "reaction") {
    return (
      <div className="space-y-4 rounded-lg border border-border/60 bg-surface-wash/25 p-4">
        {primal && (operation === "scheme-create" || operation === "panel-create") ? (
          <div>
            <Label htmlFor="pools" className="text-xs">
              PrimalScheme pools / tubes
            </Label>
            <Input
              id="pools"
              required
              type="number"
              min={1}
              value={value("pools")}
              onChange={(e) => onChange("pools", e.target.value)}
              className="mt-1 sm:max-w-sm"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              Pool assignment belongs to the selected backend. Olivar pool/SADDLE output is not
              overwritten with the PrimalScheme pool count.
            </p>
          </div>
        ) : null}
        <div>
          <Label htmlFor="schemeVersion" className="text-xs">
            Scheme version / lifecycle identity
          </Label>
          <Input
            id="schemeVersion"
            value={value("schemeVersion")}
            onChange={(e) => onChange("schemeVersion", e.target.value)}
            placeholder="e.g. v1.0.0"
            className="mt-1 sm:max-w-sm"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Major = redesign/configuration; minor = primer-sequence add/remove/change; patch = no
            primer-sequence change such as concentration rebalance.
          </p>
        </div>
        <details className="rounded-lg border border-border/60 bg-background/35 p-3">
          <summary className="cursor-pointer text-xs font-medium">
            Sequencing depth / dropout evidence
          </summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <EvidenceInput
              id="tilingMeanDepth"
              label="Mean depth"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="tilingMinimumDepth"
              label="Minimum depth"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="tilingDropoutAmplicons"
              label="Dropout amplicons"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="tilingDepthReference"
              label="Depth/BED/TSV reference"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="tilingPoolBalanceEvidence"
              label="Pool balance evidence"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="tilingVariantEscapeEvidence"
              label="Variant escape evidence"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="tilingSequencingRunId"
              label="Sequencing run ID"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="tilingValidationNotes"
              label="Validation notes"
              value={value}
              onChange={onChange}
            />
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Measured dropout evidence is input to an explicit repair workflow; it never mutates the
            original scheme in-place.
          </p>
        </details>
      </div>
    );
  }

  return (
    <div className="space-y-4 rounded-lg border border-border/60 bg-surface-wash/25 p-4">
      <div>
        <h3 className="font-serif text-base font-semibold">Tiled-scheme backend & lifecycle</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Choose the design engine explicitly. Compare runs both engines independently and reports
          disagreement; it never blends scores or primer sets.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <Label htmlFor="tilingBackend" className="text-xs">
            Primary backend
          </Label>
          <select
            id="tilingBackend"
            required
            value={backend}
            onChange={(e) => {
              const next = e.target.value;
              onChange("tilingBackend", next);
              if (next !== "primalscheme3") onChange("tilingOperation", "scheme-create");
            }}
            className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
          >
            <option value="primalscheme3">PrimalScheme3 3.3.0</option>
            <option value="olivar">Olivar 1.3.3</option>
            <option value="compare">Compare · independent side-by-side</option>
          </select>
        </div>
        <div>
          <Label htmlFor="tilingOperation" className="text-xs">
            Lifecycle operation
          </Label>
          <select
            id="tilingOperation"
            required
            value={operation}
            onChange={(e) => onChange("tilingOperation", e.target.value)}
            disabled={!primal || backend === "compare"}
            className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
          >
            <option value="scheme-create">Create new scheme</option>
            {backend === "primalscheme3" ? (
              <>
                <option value="panel-create">Create bounded panel</option>
                <option value="repair-mode">Repair with new variation</option>
                <option value="scheme-replace">Replace primer pair</option>
              </>
            ) : null}
          </select>
        </div>
        <div>
          <Label htmlFor="tilingAlignmentMode" className="text-xs">
            Alignment authority
          </Label>
          <select
            id="tilingAlignmentMode"
            required
            value={value("tilingAlignmentMode")}
            onChange={(e) => onChange("tilingAlignmentMode", e.target.value)}
            className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
          >
            <option value="">Choose</option>
            <option value="auto">Auto · pinned MAFFT policy</option>
            <option value="prealigned">Preserve reviewed MSA</option>
          </select>
        </div>
      </div>
      <div className="rounded-md border border-border/60 bg-background/35 p-2 text-xs text-muted-foreground">
        Backend authority:{" "}
        {backend === "compare"
          ? "PrimalScheme3 3.3.0 + Olivar 1.3.3, executed independently with no score/primer-set averaging"
          : String(
              (tilingRecords[backend === "olivar" ? "olivar-1.3.3" : "primalscheme3-3.3.0"] || {})
                .selection || backend,
            )}
        .
      </div>
      {backend === "primalscheme3" && operation === "panel-create" ? (
        <LifecycleText
          id="existingBed"
          label="Existing primer BED to extend — optional"
          value={value("existingBed")}
          onChange={onChange}
          placeholder="Paste existing primer BED if extending a reviewed panel."
        />
      ) : null}
      {backend === "primalscheme3" &&
      (operation === "repair-mode" || operation === "scheme-replace") ? (
        <div className="space-y-3 rounded-md border bg-background/45 p-3">
          {operation === "scheme-replace" ? (
            <EvidenceInput
              id="primerName"
              label="Primer-pair name/stem to replace"
              value={value}
              onChange={onChange}
            />
          ) : null}
          <LifecycleText
            id="existingBed"
            label="Existing primer BED — required"
            required
            value={value("existingBed")}
            onChange={onChange}
            placeholder="Paste reviewed primer BED"
          />
          <LifecycleText
            id="schemeConfig"
            label="Original PrimalScheme config.json — required"
            required
            value={value("schemeConfig")}
            onChange={onChange}
            placeholder={'{"...":"original config"}'}
          />
        </div>
      ) : null}
      <p className="text-xs leading-relaxed text-muted-foreground">
        ARTIC/PrimalScheme BED is normalised as 0-based half-open. Olivar internal coordinates are
        never imported directly; only its BED export crosses the PCRStudio coordinate boundary.
      </p>
    </div>
  );
}

function LifecycleText({
  id,
  label,
  value,
  onChange,
  placeholder,
  required = false,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (key: string, next: string) => void;
  placeholder: string;
  required?: boolean;
}) {
  const accept = id === "schemeConfig" ? ".json,application/json" : ".bed,.txt,text/plain";
  return (
    <div className="space-y-1">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Label htmlFor={id} className="text-xs">
          {label}
        </Label>
        <label className="cursor-pointer rounded-md border border-border/70 bg-background px-2 py-1 text-xs text-muted-foreground focus-within:ring-2 focus-within:ring-ring hover:text-foreground">
          Load local file
          <input
            type="file"
            accept={accept}
            className="sr-only"
            onChange={async (event) => {
              const file = event.target.files?.[0];
              if (!file) return;
              onChange(id, await file.text());
              event.currentTarget.value = "";
            }}
          />
        </label>
      </div>
      <textarea
        id={id}
        required={required}
        value={value}
        onChange={(event) => onChange(id, event.target.value)}
        placeholder={placeholder}
        spellCheck={false}
        rows={6}
        className="w-full rounded-lg border border-border/70 bg-background px-3 py-2 font-mono text-xs leading-relaxed focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      />
      <p className="text-xs leading-relaxed text-muted-foreground">
        The browser reads the selected file as text and sends its content, not a host path.
        PCRStudio hashes the imported artifact and writes it only inside the worker&apos;s temporary
        Linux workspace.
      </p>
    </div>
  );
}

function OutwardFields({
  value,
  onChange,
}: {
  value: (key: string) => string;
  onChange: (key: string, next: string) => void;
}) {
  const branch = value("inverseBranch") || "restriction-self-ligation";
  const restrictionBranch = branch === "restriction-self-ligation";
  return (
    <div className="space-y-4 rounded-lg border border-border/60 bg-surface-wash/25 p-4">
      <div>
        <h3 className="font-serif text-base font-semibold">Inverse-PCR molecule preparation</h3>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          Standard restriction/self-ligation and a supplied circular template are separate
          topologies. Enzyme/digest metadata is required only for the restriction branch; PCRStudio
          never invents it for a circle prepared elsewhere.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <Label htmlFor="inverseBranch" className="text-xs">
            Preparation branch
          </Label>
          <select
            id="inverseBranch"
            required
            value={branch}
            onChange={(e) => onChange("inverseBranch", e.target.value)}
            className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
          >
            <option value="restriction-self-ligation">Restriction digest + self-ligation</option>
            <option value="supplied-circular-template">Supplied circularized template</option>
          </select>
        </div>
        <div>
          <Label htmlFor="mappingUseCase" className="text-xs">
            Mapping use case
          </Label>
          <select
            id="mappingUseCase"
            value={value("mappingUseCase") || "generic-flank"}
            onChange={(e) => onChange("mappingUseCase", e.target.value)}
            className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
          >
            <option value="generic-flank">Unknown genomic flank</option>
            <option value="transposon-insertion">Transposon insertion mapping</option>
            <option value="integration-site">Vector / integration-site mapping</option>
          </select>
        </div>
        <div>
          <Label htmlFor="enzymeCohortSize" className="text-xs">
            Diagnostic enzyme cohort
          </Label>
          <Input
            id="enzymeCohortSize"
            type="number"
            min={1}
            max={10}
            value={value("enzymeCohortSize") || "3"}
            onChange={(e) => onChange("enzymeCohortSize", e.target.value)}
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Ranks backup enzymes as diagnostic alternatives; it does not claim an unknown-flank
            fragment length.
          </p>
        </div>
      </div>

      {restrictionBranch ? (
        <div className="space-y-3 rounded-lg border border-border/60 bg-background/35 p-3">
          <h4 className="text-sm font-semibold">Restriction/self-ligation context</h4>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <EvidenceInput
              id="enzyme"
              label="Restriction enzyme"
              value={value}
              onChange={onChange}
              placeholder="EcoRI"
            />
            <EvidenceInput
              id="methylationBranch"
              label="Methylation compatibility"
              value={value}
              onChange={onChange}
              placeholder="Reviewed / unresolved"
            />
            <div>
              <Label htmlFor="leftEndPhosphate" className="text-xs">
                Left digest-end phosphate
              </Label>
              <select
                id="leftEndPhosphate"
                required
                value={value("leftEndPhosphate")}
                onChange={(e) => onChange("leftEndPhosphate", e.target.value)}
                className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
              >
                <option value="">Choose</option>
                <option value="unresolved">Unresolved</option>
                <option value="phosphorylated">Phosphorylated</option>
                <option value="unphosphorylated">Unphosphorylated</option>
              </select>
            </div>
            <div>
              <Label htmlFor="rightEndPhosphate" className="text-xs">
                Right digest-end phosphate
              </Label>
              <select
                id="rightEndPhosphate"
                required
                value={value("rightEndPhosphate")}
                onChange={(e) => onChange("rightEndPhosphate", e.target.value)}
                className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
              >
                <option value="">Choose</option>
                <option value="unresolved">Unresolved</option>
                <option value="phosphorylated">Phosphorylated</option>
                <option value="unphosphorylated">Unphosphorylated</option>
              </select>
            </div>
            <EvidenceInput
              id="linearControlProvenance"
              label="Linear-control provenance"
              value={value}
              onChange={onChange}
              placeholder="Evidence / unresolved"
            />
          </div>
          <p className="text-xs text-muted-foreground">
            The enzyme must not cut the complete known anchor in this standard topology.
            One-sided/internal-cut IPCR remains a separate reference-only topology.
          </p>
        </div>
      ) : (
        <div className="rounded-lg border border-border/60 bg-background/35 p-3">
          <Label htmlFor="circleLength" className="text-xs">
            Known circular-template length (bp)
          </Label>
          <Input
            id="circleLength"
            required
            type="number"
            min={1}
            value={value("circleLength")}
            onChange={(e) => onChange("circleLength", e.target.value)}
            className="mt-1"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Digest enzyme, methylation and end-phosphate fields are intentionally absent for a
            supplied circle.
          </p>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <EvidenceInput
          id="circularizationProvenance"
          label="Circularization / circle provenance"
          value={value}
          onChange={onChange}
          placeholder="Ligation SOP, supplied-circle ID, revision"
        />
        <div className="grid grid-cols-2 gap-2">
          <div>
            <Label htmlFor="unknownFlankMin" className="text-xs">
              Unknown flank min (bp)
            </Label>
            <Input
              id="unknownFlankMin"
              type="number"
              min={0}
              value={value("unknownFlankMin")}
              onChange={(e) => onChange("unknownFlankMin", e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="unknownFlankMax" className="text-xs">
              Unknown flank max (bp)
            </Label>
            <Input
              id="unknownFlankMax"
              type="number"
              min={0}
              value={value("unknownFlankMax")}
              onChange={(e) => onChange("unknownFlankMax", e.target.value)}
            />
          </div>
        </div>
      </div>
      <details className="rounded-lg border border-border/60 bg-background/35 p-3">
        <summary className="cursor-pointer text-xs font-medium">
          Digest / circle / mapping evidence
        </summary>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <EvidenceInput
            id="inverseObservedBandBp"
            label="Observed band (bp)"
            type="number"
            value={value}
            onChange={onChange}
          />
          <EvidenceInput
            id="inverseDigestEvidence"
            label="Digest evidence"
            value={value}
            onChange={onChange}
          />
          <EvidenceInput
            id="inverseLigationEvidence"
            label="Ligation evidence"
            value={value}
            onChange={onChange}
          />
          <EvidenceInput
            id="inverseCircleEvidence"
            label="Circle evidence"
            value={value}
            onChange={onChange}
          />
          <EvidenceInput
            id="inverseLinearControlEvidence"
            label="Linear-control evidence"
            value={value}
            onChange={onChange}
          />
          <EvidenceInput
            id="inverseSequenceConfirmation"
            label="Sanger / sequence confirmation"
            value={value}
            onChange={onChange}
          />
          <EvidenceInput
            id="inverseMappingReference"
            label="Mapped flank reference"
            value={value}
            onChange={onChange}
          />
          <EvidenceInput
            id="inverseValidationNotes"
            label="Validation notes"
            value={value}
            onChange={onChange}
          />
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          Observed evidence is retained with <code>decision_impact = none</code>; sequencing
          confirmation can support a flank claim but never rewrites the original primer ranking.
        </p>
      </details>
    </div>
  );
}

function NestedFields({
  section,
  value,
  onChange,
}: {
  section: "design" | "reaction";
  value: (key: string) => string;
  onChange: (key: string, next: string) => void;
}) {
  if (section === "reaction") {
    const transferMode = value("transferMode") || "direct-transfer";
    return (
      <div className="space-y-4 rounded-lg border border-border/60 bg-surface-wash/25 p-4">
        <div>
          <h3 className="font-serif text-base font-semibold">Two-round reaction timeline</h3>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            Generation 1 executes two physically separate reactions. Round-specific chemistry,
            transfer and cleanup are recorded independently; none is inferred from primer geometry.
          </p>
        </div>
        <input type="hidden" id="singleTube" value="false" readOnly />
        <div className="rounded-lg border border-dashed border-border/60 bg-background/35 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
          <span className="font-medium text-foreground">Two-tube topology is enforced.</span>{" "}
          Generic one-tube nested PCR remains reference-only because it requires a distinct,
          source-backed thermal/topology contract.
        </div>

        <div className="grid gap-4 lg:grid-cols-[1fr_auto_1fr] lg:items-start">
          <div className="space-y-3 rounded-lg border border-border/60 bg-background/35 p-3">
            <h4 className="text-sm font-semibold">Round 1 · outer pair</h4>
            <EvidenceInput
              id="round1Polymerase"
              label="Polymerase / reaction identity"
              value={value}
              onChange={onChange}
              placeholder="Named product or validated SOP"
            />
            <div>
              <Label htmlFor="round1Conditions" className="text-xs">
                Round 1 numeric conditions · JSON object
              </Label>
              <textarea
                id="round1Conditions"
                rows={4}
                spellCheck={false}
                value={value("round1Conditions")}
                onChange={(e) => onChange("round1Conditions", e.target.value)}
                placeholder={'{"primer_nM": 400, "template_ng": 10}'}
                className="mt-1 w-full rounded-lg border border-border/70 bg-surface-wash/35 p-2 font-mono text-xs"
              />
            </div>
            <div>
              <Label htmlFor="round1ThermalProgram" className="text-xs">
                Round 1 thermal program · JSON array
              </Label>
              <textarea
                id="round1ThermalProgram"
                rows={5}
                spellCheck={false}
                value={value("round1ThermalProgram")}
                onChange={(e) => onChange("round1ThermalProgram", e.target.value)}
                placeholder={'[{"stage":"denaturation","temperature_c":95,"seconds":30}]'}
                className="mt-1 w-full rounded-lg border border-border/70 bg-surface-wash/35 p-2 font-mono text-xs"
              />
            </div>
          </div>

          <div
            className="hidden pt-10 text-center text-muted-foreground lg:block"
            aria-hidden="true"
          >
            →
          </div>

          <div className="space-y-3 rounded-lg border border-border/60 bg-background/35 p-3">
            <h4 className="text-sm font-semibold">Round 2 · inner pair</h4>
            <EvidenceInput
              id="round2Polymerase"
              label="Polymerase / reaction identity"
              value={value}
              onChange={onChange}
              placeholder="May differ from Round 1"
            />
            <div>
              <Label htmlFor="round2Conditions" className="text-xs">
                Round 2 numeric conditions · JSON object
              </Label>
              <textarea
                id="round2Conditions"
                rows={4}
                spellCheck={false}
                value={value("round2Conditions")}
                onChange={(e) => onChange("round2Conditions", e.target.value)}
                placeholder={'{"primer_nM": 400, "template_ul": 1}'}
                className="mt-1 w-full rounded-lg border border-border/70 bg-surface-wash/35 p-2 font-mono text-xs"
              />
            </div>
            <div>
              <Label htmlFor="round2ThermalProgram" className="text-xs">
                Round 2 thermal program · JSON array
              </Label>
              <textarea
                id="round2ThermalProgram"
                rows={5}
                spellCheck={false}
                value={value("round2ThermalProgram")}
                onChange={(e) => onChange("round2ThermalProgram", e.target.value)}
                placeholder={'[{"stage":"denaturation","temperature_c":95,"seconds":30}]'}
                className="mt-1 w-full rounded-lg border border-border/70 bg-surface-wash/35 p-2 font-mono text-xs"
              />
            </div>
          </div>
        </div>

        <div className="space-y-3 rounded-lg border border-border/60 bg-background/35 p-3">
          <h4 className="text-sm font-semibold">Transfer / cleanup</h4>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <Label htmlFor="transferMode" className="text-xs">
                Transfer mode
              </Label>
              <select
                id="transferMode"
                required
                value={transferMode}
                onChange={(e) => onChange("transferMode", e.target.value)}
                className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
              >
                <option value="direct-transfer">Direct transfer</option>
                <option value="diluted-transfer">Diluted transfer</option>
                <option value="msz-exonuclease-i">Msz Exonuclease I cleanup</option>
                <option value="thermolabile-exonuclease-i">
                  Thermolabile Exonuclease I cleanup
                </option>
                <option value="purified-product">Purified first-round product</option>
                <option value="custom-sop">Custom validated SOP</option>
              </select>
            </div>
            <EvidenceInput
              id="transferVolumeUl"
              label="Transferred volume (µL)"
              type="number"
              value={value}
              onChange={onChange}
            />
            {transferMode === "diluted-transfer" ? (
              <EvidenceInput
                id="transferDilutionFactor"
                label="Dilution factor"
                type="number"
                value={value}
                onChange={onChange}
              />
            ) : null}
          </div>
          {transferMode === "msz-exonuclease-i" || transferMode === "thermolabile-exonuclease-i" ? (
            <div>
              <Label htmlFor="cleanupProtocol" className="text-xs">
                Exact cleanup protocol
              </Label>
              <select
                id="cleanupProtocol"
                required
                value={value("cleanupProtocol")}
                onChange={(e) => onChange("cleanupProtocol", e.target.value)}
                className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
              >
                <option value="">Choose the matching named protocol</option>
                {transferMode === "msz-exonuclease-i" ? (
                  <option value="neb-msz-exonuclease-i">
                    NEB Msz Exonuclease I · nested-PCR cleanup
                  </option>
                ) : null}
                {transferMode === "thermolabile-exonuclease-i" ? (
                  <option value="neb-thermolabile-exonuclease-i">
                    NEB Thermolabile Exonuclease I · nested-PCR cleanup
                  </option>
                ) : null}
              </select>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                The selected authority owns enzyme amount, input-volume ceiling, cleanup incubation
                and heat-inactivation stages. Values are not generalized to other Exonuclease I
                products.
              </p>
            </div>
          ) : null}
          {transferMode === "custom-sop" ? (
            <EvidenceInput
              id="customTransferSop"
              label="Custom SOP identity / provenance"
              value={value}
              onChange={onChange}
              placeholder="Validated SOP ID, revision or source"
            />
          ) : null}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="carryoverPrevention" className="text-xs">
            Carry-over prevention strategy
          </Label>
          <select
            id="carryoverPrevention"
            aria-label="Carry-over prevention between rounds"
            required
            value={value("carryoverPrevention")}
            onChange={(event) => onChange("carryoverPrevention", event.target.value)}
            className="h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-3 text-sm"
          >
            <option value="">Choose or explicitly record none</option>
            <option value="not-selected">No named carry-over strategy selected</option>
            <option value="dutp-ung-strategy-only">dUTP / UNG strategy identity only</option>
          </select>
          <p className="text-xs leading-relaxed text-muted-foreground">
            PCRStudio does not invent dUTP substitution, UNG amount, incubation or inactivation
            without a separately named chemistry authority.
          </p>
        </div>

        <details className="rounded-lg border border-border/60 bg-background/35 p-3">
          <summary className="cursor-pointer text-xs font-medium">
            Nested-PCR run and contamination evidence
          </summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <EvidenceInput
              id="nestedRound1Ntc"
              label="Round-1 NTC"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="nestedRound2Ntc"
              label="Round-2 NTC"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="nestedPositiveControl"
              label="Positive control"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="nestedPrePcrArea"
              label="Pre-PCR area / workflow"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="nestedRound1Area"
              label="Round-1 area"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="nestedTransferArea"
              label="Transfer area"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="nestedRound2Area"
              label="Round-2 area"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="nestedTransferRunId"
              label="Transfer / run ID"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="nestedSourceTubeWell"
              label="Source tube / well"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="nestedDestinationTubeWell"
              label="Destination tube / well"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="nestedRound1ObservedBandBp"
              label="Round-1 observed band (bp)"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="nestedRound2ObservedBandBp"
              label="Round-2 observed band (bp)"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="nestedSequenceConfirmation"
              label="Sequence confirmation"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="nestedRawDataReference"
              label="Raw-data reference"
              value={value}
              onChange={onChange}
            />
          </div>
          <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
            These observations are evidence only (<code>decision_impact = none</code>); they never
            rewrite primer ranking in the original design run.
          </p>
        </details>
      </div>
    );
  }

  return (
    <div className="space-y-4 rounded-lg border border-border/60 bg-surface-wash/25 p-4">
      <div>
        <h3 className="font-serif text-base font-semibold">Nested-pair architecture</h3>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          The first-round pair defines the outer product; the second pair must lie inside it. These
          are coupled geometric constraints and therefore live on Design rather than Target or
          Reaction.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Round
          title="First round"
          prefix="outer"
          value={value}
          onChange={onChange}
          placeholders={["800", "1500"]}
        />
        <Round
          title="Second round"
          prefix="inner"
          value={value}
          onChange={onChange}
          placeholders={["300", "700"]}
        />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="shares" className="text-xs">
            Does the second round reuse a primer?
          </Label>
          <select
            id="shares"
            aria-label="Does the second round reuse a primer"
            required
            value={value("shares")}
            onChange={(event) => onChange("shares", event.target.value)}
            className="h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-3 text-sm"
          >
            <option value="">Choose the round relationship</option>
            <option value="nothing">No — both primers are new</option>
            <option value="forward">Yes, the forward one</option>
            <option value="reverse">Yes, the reverse one</option>
          </select>
          <p className="text-xs leading-relaxed text-muted-foreground">
            A shared primer creates a semi-nested two-tube assay; it is not a one-tube topology.
          </p>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="margin" className="text-xs">
            How far inside, at least
          </Label>
          <Input
            id="margin"
            aria-label="Minimum distance inside"
            required
            type="number"
            min={0}
            value={value("margin")}
            onChange={(event) => onChange("margin", event.target.value)}
            placeholder="0 means non-overlap only"
          />
          <p className="text-xs leading-relaxed text-muted-foreground">
            Zero means only that inner primers may not overlap the outer primers; no universal
            published margin is invented.
          </p>
        </div>
      </div>
    </div>
  );
}

function Round({
  title,
  prefix,
  value,
  onChange,
  placeholders,
}: {
  title: string;
  prefix: string;
  value: (key: string) => string;
  onChange: (key: string, next: string) => void;
  placeholders: [string, string];
}) {
  return (
    <div className="space-y-2">
      <h4 className="text-xs font-medium">{title}</h4>
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1">
          <Label htmlFor={`${prefix}-product-min`} className="text-xs text-muted-foreground">
            Shortest
          </Label>
          <Input
            id={`${prefix}-product-min`}
            aria-label={`${prefix} product shortest`}
            type="number"
            min={50}
            value={value(`${prefix}_product_min`)}
            onChange={(event) => onChange(`${prefix}_product_min`, event.target.value)}
            placeholder={placeholders[0]}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor={`${prefix}-product-max`} className="text-xs text-muted-foreground">
            Longest
          </Label>
          <Input
            id={`${prefix}-product-max`}
            aria-label={`${prefix} product longest`}
            type="number"
            min={50}
            value={value(`${prefix}_product_max`)}
            onChange={(event) => onChange(`${prefix}_product_max`, event.target.value)}
            placeholder={placeholders[1]}
          />
        </div>
      </div>
    </div>
  );
}

/** Canonical ownership registry for every engine/module-specific form family. */
const ENGINE_FIELD_RULES: readonly EngineFieldRule[] = [
  {
    engine: "loop-set",
    section: "target",
    render: ({ value, onChange }) => <LampTargetFields value={value} onChange={onChange} />,
  },
  {
    engine: "flanking-pair",
    section: "target",
    modules: ["colony-pcr"],
    render: ({ value, onChange }) => <ColonyHostFields value={value} onChange={onChange} />,
  },
  {
    engine: "flanking-pair",
    section: "target",
    modules: ["digital-pcr"],
    render: ({ value, onChange }) => (
      <DigitalFragmentationFields value={value} onChange={onChange} />
    ),
  },
  {
    engine: "outward-pair",
    section: "strategy",
    render: ({ engine, moduleId, section, value, onChange }) => (
      <>
        <OutwardFields value={value} onChange={onChange} />
        <EngineClosureFields
          engine={engine}
          moduleId={moduleId}
          section={section}
          value={value}
          onChange={onChange}
        />
      </>
    ),
  },
  {
    engine: "tiling-scheme",
    section: "strategy",
    render: ({ value, onChange }) => (
      <SchemeFields section="strategy" value={value} onChange={onChange} />
    ),
  },
  {
    engine: "nested",
    section: "design",
    render: ({ value, onChange }) => (
      <NestedFields section="design" value={value} onChange={onChange} />
    ),
  },
  {
    engine: "mutagenic-pair",
    section: "design",
    render: ({ value, onChange }) => (
      <EditFields section="design" value={value} onChange={onChange} />
    ),
  },
  {
    engine: "single-primer",
    section: "design",
    render: ({ engine, moduleId, section, value, onChange }) => (
      <>
        <ReadFields section="design" moduleId={moduleId} value={value} onChange={onChange} />
        <EngineClosureFields
          engine={engine}
          moduleId={moduleId}
          section={section}
          value={value}
          onChange={onChange}
        />
      </>
    ),
  },
  {
    engine: "tiling-scheme",
    section: "design",
    render: ({ engine, moduleId, section, value, onChange }) => (
      <>
        <SchemeFields section="design" value={value} onChange={onChange} />
        <EngineClosureFields
          engine={engine}
          moduleId={moduleId}
          section={section}
          value={value}
          onChange={onChange}
        />
      </>
    ),
  },
  {
    engine: "junction-primers",
    section: "design",
    render: ({ value, onChange }) => (
      <AssemblyFields section="design" value={value} onChange={onChange} />
    ),
  },
  {
    engine: "discriminating-pair",
    section: "design",
    render: ({ moduleId, value, onChange }) => (
      <VariantFields section="design" moduleId={moduleId} value={value} onChange={onChange} />
    ),
  },
  {
    engine: "loop-set",
    section: "design",
    render: ({ value, onChange }) => <LoopFields value={value} onChange={onChange} />,
  },
  {
    engine: "pair-and-probe",
    section: "design",
    render: ({ value, onChange }) => (
      <ProbeFields section="design" value={value} onChange={onChange} />
    ),
  },
  {
    engine: "consensus-pair",
    section: "design",
    render: ({ value, onChange }) => <ConsensusFields value={value} onChange={onChange} />,
  },
  {
    engine: "nested",
    section: "reaction",
    render: ({ value, onChange }) => (
      <NestedFields section="reaction" value={value} onChange={onChange} />
    ),
  },
  {
    engine: "mutagenic-pair",
    section: "reaction",
    render: ({ value, onChange }) => (
      <EditFields section="reaction" value={value} onChange={onChange} />
    ),
  },
  {
    engine: "single-primer",
    section: "reaction",
    render: ({ engine, moduleId, section, value, onChange }) => (
      <>
        <ReadFields section="reaction" moduleId={moduleId} value={value} onChange={onChange} />
        <EngineClosureFields
          engine={engine}
          moduleId={moduleId}
          section={section}
          value={value}
          onChange={onChange}
        />
      </>
    ),
  },
  {
    engine: "tiling-scheme",
    section: "reaction",
    render: ({ engine, moduleId, section, value, onChange }) => (
      <>
        <SchemeFields section="reaction" value={value} onChange={onChange} />
        <EngineClosureFields
          engine={engine}
          moduleId={moduleId}
          section={section}
          value={value}
          onChange={onChange}
        />
      </>
    ),
  },
  {
    engine: "junction-primers",
    section: "reaction",
    render: ({ value, onChange }) => (
      <AssemblyFields section="reaction" value={value} onChange={onChange} />
    ),
  },
  {
    engine: "discriminating-pair",
    section: "reaction",
    render: ({ moduleId, value, onChange }) => (
      <VariantFields section="reaction" moduleId={moduleId} value={value} onChange={onChange} />
    ),
  },
  {
    engine: "pair-and-probe",
    section: "reaction",
    render: ({ value, onChange }) => (
      <ProbeFields section="reaction" value={value} onChange={onChange} />
    ),
  },
  {
    engine: "consensus-pair",
    section: "reaction",
    render: ({ value, onChange }) => <ConsensusReactionFields value={value} onChange={onChange} />,
  },
  {
    engine: "loop-set",
    section: "reaction",
    render: ({ value, onChange }) => <LampReactionFields value={value} onChange={onChange} />,
  },
  {
    engine: "flanking-pair",
    section: "reaction",
    modules: ["standard-pcr"],
    render: ({ value, onChange }) => <StandardPcrFields value={value} onChange={onChange} />,
  },
  {
    engine: "flanking-pair",
    section: "reaction",
    modules: ["colony-pcr"],
    render: ({ value, onChange }) => <ColonyPcrFields value={value} onChange={onChange} />,
  },
  {
    engine: "flanking-pair",
    section: "reaction",
    modules: ["long-range-pcr"],
    render: ({ value, onChange }) => <LongRangePcrFields value={value} onChange={onChange} />,
  },
  {
    engine: "flanking-pair",
    section: "reaction",
    modules: ["qpcr-sybr"],
    render: ({ value, onChange }) => <QpcrSybrFields value={value} onChange={onChange} />,
  },
  {
    engine: "flanking-pair",
    section: "reaction",
    modules: ["rpa"],
    render: ({ value, onChange }) => <RpaFields value={value} onChange={onChange} />,
  },
  {
    engine: "flanking-pair",
    section: "reaction",
    modules: ["digital-pcr"],
    render: ({ value, onChange }) => <DigitalPcrFields value={value} onChange={onChange} />,
  },
  {
    engine: "flanking-pair",
    section: "reaction",
    modules: ["restriction-cloning"],
    render: ({ value, onChange }) => (
      <RestrictionCloningWorkflowFields value={value} onChange={onChange} />
    ),
  },
] as const;

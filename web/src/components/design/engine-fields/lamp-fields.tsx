"use client";

import { useRef, useState } from "react";
import { LampMultiplexEditor } from "./lamp-multiplex-editor";

/** LAMP-specific design/reaction controls, isolated from the generic engine router. */
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  LAMP_PROTOCOL_METADATA,
  LAMP_PROTOCOLS,
  LAMP_DESIGN_STAGES,
  LAMP_MUTATION_ANCHORS,
} from "@/lib/lamp-protocol-authority.generated";
import {
  LAMP_BENCH_FIELD_MAP,
  lampBenchOptimizationRange,
  lampProtocolDirectMatrix,
  lampProtocolForbidsChemistry,
  lampProtocolForbidsReadout,
  lampProtocolFormulationAllowed,
  lampProtocolSupportsSubstrate,
  lampReadoutChemistryBranch,
  lampScenarioIssueOwner,
  lampScenarioIssues,
  resolveLampNumericPreview,
} from "@/lib/lamp-contract";

const LAMP_PROTOCOL_OPTIONS = LAMP_PROTOCOLS.filter((id) => id !== "not-selected").map((id) => ({
  id,
  ...(LAMP_PROTOCOL_METADATA[id as keyof typeof LAMP_PROTOCOL_METADATA] as {
    selection: string;
    vendor: string;
    kit_id?: string;
    source_url?: string;
    source_revision?: string;
    source_reviewed_date?: string;
    numeric_authority_status?: string;
    lifecycle?: { status?: string; snapshot?: string; availability_claim?: string; note?: string };
  }),
}));

function lampProtocolVendorGroups(showHistorical: boolean, selected: string) {
  const visible = LAMP_PROTOCOL_OPTIONS.filter((option) => {
    const status = option.lifecycle?.status ?? "reviewed-at-catalogue-snapshot";
    const historical =
      status === "historical" || status === "superseded" || status === "discontinued";
    return !historical || showHistorical || option.id === selected;
  });
  return Object.entries(
    visible.reduce<Record<string, typeof LAMP_PROTOCOL_OPTIONS>>((groups, option) => {
      const vendor = option.vendor || "Other";
      (groups[vendor] ??= []).push(option);
      return groups;
    }, {}),
  ).sort(([a], [b]) => a.localeCompare(b));
}

export function LampReactionFields({
  value,
  onChange,
}: {
  value: (key: string) => string;
  onChange: (key: string, next: string) => void;
}) {
  const protocol = value("lampProtocol");
  const [showHistoricalProtocols, setShowHistoricalProtocols] = useState(false);
  const protocolVendorGroups = lampProtocolVendorGroups(showHistoricalProtocols, protocol);
  const selectedProtocolMetadata = LAMP_PROTOCOL_OPTIONS.find((option) => option.id === protocol);
  const fromRna = value("fromRna") === "true";
  const protocolDisabled = (id: string) => !lampProtocolSupportsSubstrate(id, fromRna);
  const protocolSubstrateIncompatible =
    Boolean(protocol) && !lampProtocolSupportsSubstrate(protocol, fromRna);
  const pyrophosphataseProtocol = lampProtocolForbidsReadout(protocol, "turbidity");
  const m1712 = protocol === "neb-m1712";
  const readout = value("lampReadout") || "not-specified";
  const chemistry = value("lampReadoutChemistry") || "not-specified";
  const formulation = value("lampFormulation") || "not-specified";
  const preparation = value("lampSamplePreparation") || "not-specified";
  const matrix = value("lampSampleMatrix") || "not-specified";
  const directAuthority = lampProtocolDirectMatrix(protocol);
  const directPreparation =
    preparation === "direct-addition" || preparation === "koh-lyse-and-lamp";
  const chemistryBranch = lampReadoutChemistryBranch(chemistry);
  const benchValues = Object.fromEntries(LAMP_BENCH_FIELD_MAP.map(([wire]) => [wire, value(wire)]));
  const scenarioIssues = lampScenarioIssues({
    protocol,
    fromRna,
    matrix,
    preparation,
    formulation,
    readout,
    chemistry,
    designIntent: value("lampDesignIntent") || "standard",
    inclusivity: value("inclusivity"),
    benchValues,
    carryoverStrategy: value("lampCarryoverStrategy") || "protocol-default",
    reconstitutionX: value("lampReconstitutionX") || "protocol-default",
    specificityAdditive: value("lampSpecificityAdditive") || "none",
    accelerationAdditive: value("lampAccelerationAdditive") || "none",
    primerKineticsProfile: value("lampPrimerKineticsProfile") || "protocol-default",
    preincubationStrategy: value("lampPreincubationStrategy") || "protocol-default",
    sampleInputPercent: value("lampSampleInputPercent"),
    sampleBufferType: value("lampSampleBufferType") || "none",
    sampleBufferPh: value("lampSampleBufferPh"),
    sampleBufferPercent: value("lampSampleBufferPercent"),
    transportMediumPercent: value("lampTransportMediumPercent"),
    bileSaltMgMl: value("lampBileSaltMgMl"),
    caryBlairPercent: value("lampCaryBlairPercent"),
    upstreamGuanidineMm: value("lampUpstreamGuanidineMm"),
    instrumentProfile: value("lampInstrumentProfile") || "not-specified",
  });
  const reactionScenarioIssues = scenarioIssues.filter(
    (issue) => lampScenarioIssueOwner(issue) === "reaction",
  );
  const reactionIssueFields = new Set(reactionScenarioIssues.map((issue) => issue.field));
  const numericPreviewInput = {
    protocol,
    fromRna,
    matrix,
    preparation,
    formulation,
    readout,
    chemistry,
    designIntent: value("lampDesignIntent") || "standard",
    inclusivity: value("inclusivity"),
    benchValues,
    carryoverStrategy: value("lampCarryoverStrategy") || "protocol-default",
    reconstitutionX: value("lampReconstitutionX") || "protocol-default",
    specificityAdditive: value("lampSpecificityAdditive") || "none",
    accelerationAdditive: value("lampAccelerationAdditive") || "none",
    primerKineticsProfile: value("lampPrimerKineticsProfile") || "protocol-default",
    preincubationStrategy: value("lampPreincubationStrategy") || "protocol-default",
    sampleInputPercent: value("lampSampleInputPercent"),
    sampleBufferType: value("lampSampleBufferType") || "none",
    sampleBufferPh: value("lampSampleBufferPh"),
    sampleBufferPercent: value("lampSampleBufferPercent"),
    transportMediumPercent: value("lampTransportMediumPercent"),
    bileSaltMgMl: value("lampBileSaltMgMl"),
    caryBlairPercent: value("lampCaryBlairPercent"),
    upstreamGuanidineMm: value("lampUpstreamGuanidineMm"),
    instrumentProfile: value("lampInstrumentProfile") || "not-specified",
  };
  const numericPreview = resolveLampNumericPreview(numericPreviewInput);
  const [protocolSearch, setProtocolSearch] = useState("");
  const protocolSelectRef = useRef<HTMLSelectElement>(null);
  const normalizedProtocolSearch = protocolSearch.trim().toLocaleLowerCase();
  const protocolSearchMatches = normalizedProtocolSearch
    ? LAMP_PROTOCOL_OPTIONS.filter((option) =>
        `${option.selection} ${option.vendor} ${option.id}`
          .toLocaleLowerCase()
          .includes(normalizedProtocolSearch),
      )
        .slice(0, 10)
        .map((option) => ({
          value: option.id,
          text: `${option.kit_id ? `${option.kit_id} · ` : ""}${option.selection}`,
          disabled: protocolDisabled(option.id),
        }))
    : [];
  return (
    <div className="space-y-4 rounded-lg border border-border/60 bg-surface-wash/25 p-4">
      <div className="space-y-1">
        <h3 className="font-serif text-base font-semibold">
          Bench chemistry, specimen and readout
        </h3>
        <p className="text-xs leading-relaxed text-muted-foreground">
          A named protocol is bench authority only. Sample tolerance, formulation and readout are
          recorded separately and never silently change LAMP sequence ranking.
        </p>
      </div>
      <div>
        <Label htmlFor="lampProtocolSearch" className="text-xs">
          Find LAMP chemistry
        </Label>
        <Input
          id="lampProtocolSearch"
          type="search"
          value={protocolSearch}
          onChange={(event) => setProtocolSearch(event.target.value)}
          placeholder="Search vendor, catalogue ID or product name…"
          className="mt-1 sm:max-w-2xl"
          autoComplete="off"
        />
        {normalizedProtocolSearch ? (
          <div
            className="mt-2 max-h-52 space-y-1 overflow-y-auto rounded-lg border border-border/60 bg-background p-1 sm:max-w-2xl"
            role="group"
            aria-label="Matching LAMP chemistries"
          >
            {protocolSearchMatches.length ? (
              protocolSearchMatches.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  aria-pressed={protocol === option.value}
                  disabled={option.disabled}
                  className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-xs hover:bg-surface-wash/60 disabled:cursor-not-allowed disabled:opacity-45"
                  onClick={() => {
                    onChange("lampProtocol", option.value);
                    setProtocolSearch("");
                  }}
                >
                  <span>{option.text}</span>
                  <span className="ml-3 font-mono text-xs text-muted-foreground">
                    {option.value}
                  </span>
                </button>
              ))
            ) : (
              <p className="px-2 py-1.5 text-xs text-muted-foreground">
                No reviewed chemistry matches this search.
              </p>
            )}
          </div>
        ) : null}
        <Label htmlFor="lampProtocol" className="mt-3 block text-xs">
          Named LAMP / RT-LAMP chemistry
        </Label>
        <select
          ref={protocolSelectRef}
          id="lampProtocol"
          value={protocol}
          aria-invalid={protocolSubstrateIncompatible}
          onChange={(e) => onChange("lampProtocol", e.target.value)}
          className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm sm:max-w-2xl"
        >
          <option value="">Not selected · generic screening context only</option>
          {protocolVendorGroups.map(([vendor, options]) => (
            <optgroup key={vendor} label={vendor}>
              {(options ?? []).map((option) => (
                <option key={option.id} value={option.id} disabled={protocolDisabled(option.id)}>
                  {option.kit_id ? `${option.kit_id} · ` : ""}
                  {option.selection}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <label className="inline-flex min-h-6 items-center gap-2">
            <input
              type="checkbox"
              checked={showHistoricalProtocols}
              onChange={(e) => setShowHistoricalProtocols(e.target.checked)}
            />
            Show historical/superseded chemistries
          </label>
          {selectedProtocolMetadata?.source_url ? (
            <a
              className="underline underline-offset-2"
              href={selectedProtocolMetadata.source_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Official source
            </a>
          ) : null}
          {selectedProtocolMetadata?.source_revision ? (
            <span>Revision: {selectedProtocolMetadata.source_revision}</span>
          ) : null}
          {selectedProtocolMetadata?.source_reviewed_date ? (
            <span>Reviewed: {selectedProtocolMetadata.source_reviewed_date}</span>
          ) : null}
          {selectedProtocolMetadata?.lifecycle?.status ? (
            <span>Lifecycle: {selectedProtocolMetadata.lifecycle.status}</span>
          ) : null}
        </div>
        {protocolSubstrateIncompatible ? (
          <p role="alert" className="mt-1 text-xs text-destructive">
            The selected named chemistry does not support the current {fromRna ? "RNA" : "DNA"}{" "}
            substrate.
          </p>
        ) : null}
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <Label htmlFor="lampSampleMatrix" className="text-xs">
            Sample matrix
          </Label>
          <select
            id="lampSampleMatrix"
            aria-invalid={reactionIssueFields.has("lampSampleMatrix")}
            value={matrix}
            onChange={(e) => onChange("lampSampleMatrix", e.target.value)}
            className="mt-1 h-9 w-full rounded-lg border bg-surface-wash/35 px-2 text-sm"
          >
            <option value="not-specified">Not specified</option>
            <option
              value="purified-nucleic-acid"
              disabled={directPreparation && directAuthority !== "purified-nucleic-acid"}
            >
              Purified nucleic acid
            </option>
            <option value="crude-unspecified" disabled={directPreparation}>
              Crude · unresolved matrix
            </option>
            <option
              value="saliva-sputum"
              disabled={directPreparation && directAuthority !== "saliva-sputum"}
            >
              Saliva / sputum
            </option>
            <option
              value="blood-plasma-serum"
              disabled={directPreparation && directAuthority !== "blood-plasma-serum"}
            >
              Blood / plasma / serum
            </option>
            <option value="stool" disabled={directPreparation && directAuthority !== "stool"}>
              Stool
            </option>
            <option value="urine" disabled={directPreparation && directAuthority !== "urine"}>
              Urine
            </option>
            <option
              value="koh-lysate"
              disabled={directPreparation && directAuthority !== "koh-lysate"}
            >
              KOH lysate
            </option>
            <option value="other-validated" disabled={directPreparation}>
              Other validated matrix
            </option>
          </select>
        </div>
        <div>
          <Label htmlFor="lampSamplePreparation" className="text-xs">
            Sample preparation
          </Label>
          <select
            id="lampSamplePreparation"
            aria-invalid={reactionIssueFields.has("lampSamplePreparation")}
            value={preparation}
            onChange={(e) => onChange("lampSamplePreparation", e.target.value)}
            className="mt-1 h-9 w-full rounded-lg border bg-surface-wash/35 px-2 text-sm"
          >
            <option value="not-specified">Not specified</option>
            <option value="purified">Purified</option>
            <option value="extracted-crude">Extracted crude</option>
            <option value="direct-addition" disabled={!directAuthority}>
              Direct specimen addition
              {!directAuthority ? " · select a reviewed direct protocol" : ""}
            </option>
            <option value="koh-lyse-and-lamp" disabled={directAuthority !== "koh-lysate"}>
              KOH Lyse & LAMP{directAuthority !== "koh-lysate" ? " · requires KOH authority" : ""}
            </option>
            <option value="other-validated">Other validated</option>
          </select>
        </div>
        <div>
          <Label htmlFor="lampFormulation" className="text-xs">
            Formulation
          </Label>
          <select
            id="lampFormulation"
            aria-invalid={reactionIssueFields.has("lampFormulation")}
            value={formulation}
            onChange={(e) => onChange("lampFormulation", e.target.value)}
            className="mt-1 h-9 w-full rounded-lg border bg-surface-wash/35 px-2 text-sm"
          >
            <option value="not-specified">Not specified</option>
            <option value="liquid" disabled={!lampProtocolFormulationAllowed(protocol, "liquid")}>
              Liquid
            </option>
            <option
              value="lyophilized"
              disabled={!lampProtocolFormulationAllowed(protocol, "lyophilized")}
            >
              Lyophilized
            </option>
            <option
              value="air-dryable"
              disabled={!lampProtocolFormulationAllowed(protocol, "air-dryable")}
            >
              Air-dryable
            </option>
            <option
              value="dry-reagent"
              disabled={!lampProtocolFormulationAllowed(protocol, "dry-reagent")}
            >
              Dry reagent
            </option>
            <option
              value="assembled-enzyme"
              disabled={!lampProtocolFormulationAllowed(protocol, "assembled-enzyme")}
            >
              Assembled enzyme system
            </option>
          </select>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <Label htmlFor="lampReadout" className="text-xs">
            Readout
          </Label>
          <select
            id="lampReadout"
            aria-invalid={reactionIssueFields.has("lampReadout")}
            value={readout}
            onChange={(e) => onChange("lampReadout", e.target.value)}
            className="mt-1 h-9 w-full rounded-lg border bg-surface-wash/35 px-2 text-sm"
          >
            <option value="not-specified">Not specified</option>
            <option
              value="fluorescence"
              disabled={chemistry !== "not-specified" && chemistryBranch !== "fluorescence"}
            >
              Fluorescence
            </option>
            <option
              value="colorimetric"
              disabled={chemistry !== "not-specified" && chemistryBranch !== "colorimetric"}
            >
              Colorimetric
            </option>
            <option
              value="turbidity"
              disabled={
                pyrophosphataseProtocol ||
                (chemistry !== "not-specified" && chemistryBranch !== "turbidity")
              }
            >
              Turbidity{pyrophosphataseProtocol ? " · incompatible" : ""}
            </option>
            <option
              value="other-validated"
              disabled={chemistry !== "not-specified" && chemistryBranch !== "other-validated"}
            >
              Other validated
            </option>
          </select>
        </div>
        <div>
          <Label htmlFor="lampReadoutChemistry" className="text-xs">
            Exact readout chemistry
          </Label>
          <select
            id="lampReadoutChemistry"
            aria-invalid={reactionIssueFields.has("lampReadoutChemistry")}
            value={chemistry}
            onChange={(e) => onChange("lampReadoutChemistry", e.target.value)}
            className="mt-1 h-9 w-full rounded-lg border bg-surface-wash/35 px-2 text-sm"
          >
            <option value="not-specified">Not specified</option>
            {(
              [
                ["supplied-intercalating-dye", "Vendor-supplied intercalating dye"],
                ["syto9", "SYTO 9"],
                ["syto82", "SYTO 82"],
                ["tb-green", "TB Green · Takara fluorescence / FAM channel"],
                ["nzy-speedy-lamp-dye", "NZY Speedy LAMP Dye"],
                ["eiken-fd-lmp221", "Eiken LMP221 fluorescent detection reagent"],
                ["calcein", "Calcein"],
                [
                  "hydroxynaphthol-blue",
                  `Hydroxynaphthol blue${m1712 ? " · not recommended for M1712" : ""}`,
                ],
                ["eriochrome-black-t", "Eriochrome Black T"],
                ["ph-colorimetric", "pH colorimetric"],
                ["vendor-visual-color-change", "Vendor visual chemistry"],
                [
                  "turbidity-pyrophosphate",
                  `Pyrophosphate turbidity${pyrophosphataseProtocol ? " · incompatible" : ""}`,
                ],
                ["agarose-gel-endpoint", "Agarose-gel endpoint"],
                ["other-validated", "Other validated"],
              ] as const
            ).map(([id, label]) => {
              const branch = lampReadoutChemistryBranch(id);
              const disabled =
                lampProtocolForbidsChemistry(protocol, id) ||
                (readout !== "not-specified" && branch !== readout);
              return (
                <option key={id} value={id} disabled={disabled}>
                  {label}
                </option>
              );
            })}
          </select>
        </div>
        <div>
          <Label htmlFor="lampConfirmationMode" className="text-xs">
            Confirmation
          </Label>
          <select
            id="lampConfirmationMode"
            value={value("lampConfirmationMode") || "not-specified"}
            onChange={(e) => onChange("lampConfirmationMode", e.target.value)}
            className="mt-1 h-9 w-full rounded-lg border bg-surface-wash/35 px-2 text-sm"
          >
            <option value="not-specified">Not specified</option>
            <option value="none">No additional confirmation</option>
            <option value="anneal-curve">Anneal curve</option>
            <option value="melt-denaturation-curve">Melt / denaturation curve</option>
            <option value="gel-ladder">Gel ladder pattern</option>
            <option value="sequence-confirmation">Sequence confirmation</option>
            <option value="other-validated">Other validated</option>
          </select>
        </div>
      </div>
      <div>
        <Label htmlFor="lampDetectionTopology" className="text-xs">
          Detection topology
        </Label>
        <select
          id="lampDetectionTopology"
          value={value("lampDetectionTopology") || "nonspecific-dsdna"}
          onChange={(e) => onChange("lampDetectionTopology", e.target.value)}
          className="mt-1 h-9 w-full rounded-lg border bg-surface-wash/35 px-2 text-sm sm:max-w-lg"
        >
          <option value="nonspecific-dsdna">Non-specific dsDNA / standard LAMP</option>
          <option value="sequence-specific-probe" disabled>
            Sequence-specific probe · planned / fail-closed
          </option>
          <option value="multiplex-modified-primer-probe">
            Multiplex modified-primer/probe · planning/evidence only
          </option>
          <option value="lateral-flow-modified-primer" disabled>
            Lateral-flow modified primer · planned
          </option>
        </select>
        {value("lampDetectionTopology") === "multiplex-modified-primer-probe" ? (
          <div className="mt-2">
            <LampMultiplexEditor
              rawValue={value("lampMultiplexPlan")}
              onChange={(next) => onChange("lampMultiplexPlan", next)}
            />
          </div>
        ) : null}
      </div>
      <details open className="rounded-lg border border-border/50 p-3">
        <summary className="min-h-6 cursor-pointer py-1 text-sm font-medium">
          Conditional numeric recipe context
        </summary>
        <p className="mt-2 text-xs text-muted-foreground">
          These choices can change source-backed reaction numbers. Unsupported combinations fail
          closed; an absent public amount remains unresolved rather than being guessed.
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <Label htmlFor="lampInstrumentProfile" className="text-xs">
              Instrument profile
            </Label>
            <select
              id="lampInstrumentProfile"
              aria-invalid={reactionIssueFields.has("lampInstrumentProfile")}
              value={value("lampInstrumentProfile") || "not-specified"}
              onChange={(e) => onChange("lampInstrumentProfile", e.target.value)}
              className="mt-1 h-9 w-full rounded-lg border bg-surface-wash/35 px-2 text-sm"
            >
              <option value="not-specified">Not specified</option>
              <option value="vazyme-slan96p">Vazyme · SLAN-96P</option>
              <option value="vazyme-quantstudio3">Vazyme · QuantStudio 3</option>
              <option value="vazyme-quantstudio5">Vazyme · QuantStudio 5</option>
              <option value="vazyme-steponeplus">Vazyme · StepOnePlus</option>
              <option value="vazyme-lightcycler96">Vazyme · LightCycler 96</option>
              <option value="vazyme-cfx96-touch">Vazyme · CFX96 Touch</option>
              <option value="vazyme-quantgene9600">Vazyme · QuantGene 9600</option>
              <option value="vazyme-gentier96r">Vazyme · Gentier 96R</option>
              <option value="agdia-amplifire">Agdia · AmpliFire</option>
              <option value="other-qpcr">Other qPCR instrument</option>
              <option value="other-validated">Other validated</option>
            </select>
          </div>
          <div>
            <Label htmlFor="lampCarryoverStrategy" className="text-xs">
              Carry-over numeric branch
            </Label>
            <select
              id="lampCarryoverStrategy"
              aria-invalid={reactionIssueFields.has("lampCarryoverStrategy")}
              value={value("lampCarryoverStrategy") || "protocol-default"}
              onChange={(e) => onChange("lampCarryoverStrategy", e.target.value)}
              className="mt-1 h-9 w-full rounded-lg border bg-surface-wash/35 px-2 text-sm"
            >
              <option value="protocol-default">Protocol default</option>
              <option value="reviewed-dutp-udg">Reviewed dUTP + UDG overlay</option>
            </select>
          </div>
          <div>
            <Label htmlFor="lampReconstitutionX" className="text-xs">
              Reconstitution authority
            </Label>
            <select
              id="lampReconstitutionX"
              aria-invalid={reactionIssueFields.has("lampReconstitutionX")}
              value={value("lampReconstitutionX") || "protocol-default"}
              onChange={(e) => onChange("lampReconstitutionX", e.target.value)}
              className="mt-1 h-9 w-full rounded-lg border bg-surface-wash/35 px-2 text-sm"
            >
              <option value="protocol-default">Protocol default</option>
              <option value="2x">2X</option>
              <option value="4x">4X</option>
            </select>
          </div>
          <div>
            <Label htmlFor="lampSpecificityAdditive" className="text-xs">
              Specificity additive
            </Label>
            <select
              id="lampSpecificityAdditive"
              aria-invalid={reactionIssueFields.has("lampSpecificityAdditive")}
              value={value("lampSpecificityAdditive") || "none"}
              onChange={(e) => onChange("lampSpecificityAdditive", e.target.value)}
              className="mt-1 h-9 w-full rounded-lg border bg-surface-wash/35 px-2 text-sm"
            >
              <option value="none">None</option>
              <option value="tte-uvrd-reviewed">Tte UvrD · reviewed example</option>
            </select>
          </div>
          <div>
            <Label htmlFor="lampAccelerationAdditive" className="text-xs">
              Acceleration additive
            </Label>
            <select
              id="lampAccelerationAdditive"
              aria-invalid={reactionIssueFields.has("lampAccelerationAdditive")}
              value={value("lampAccelerationAdditive") || "none"}
              onChange={(e) => onChange("lampAccelerationAdditive", e.target.value)}
              className="mt-1 h-9 w-full rounded-lg border bg-surface-wash/35 px-2 text-sm"
            >
              <option value="none">None</option>
              <option value="guanidine-hcl-40mm">Guanidine HCl · 40 mM</option>
            </select>
          </div>
          <div>
            <Label htmlFor="lampPrimerKineticsProfile" className="text-xs">
              Primer kinetics profile
            </Label>
            <select
              id="lampPrimerKineticsProfile"
              aria-invalid={reactionIssueFields.has("lampPrimerKineticsProfile")}
              value={value("lampPrimerKineticsProfile") || "protocol-default"}
              onChange={(e) => onChange("lampPrimerKineticsProfile", e.target.value)}
              className="mt-1 h-9 w-full rounded-lg border bg-surface-wash/35 px-2 text-sm"
            >
              <option value="protocol-default">Protocol default</option>
              <option value="optigene-standard">OptiGene standard</option>
              <option value="optigene-high">OptiGene high-primer</option>
            </select>
          </div>
          <div>
            <Label htmlFor="lampPreincubationStrategy" className="text-xs">
              Pre-incubation
            </Label>
            <select
              id="lampPreincubationStrategy"
              aria-invalid={reactionIssueFields.has("lampPreincubationStrategy")}
              value={value("lampPreincubationStrategy") || "protocol-default"}
              onChange={(e) => onChange("lampPreincubationStrategy", e.target.value)}
              className="mt-1 h-9 w-full rounded-lg border bg-surface-wash/35 px-2 text-sm"
            >
              <option value="protocol-default">Protocol default</option>
              <option value="takara-ung-25c-10min">Takara UNG · 25°C / 10 min</option>
            </select>
          </div>
          <div>
            <Label htmlFor="lampSampleBufferType" className="text-xs">
              Sample buffer
            </Label>
            <select
              id="lampSampleBufferType"
              aria-invalid={reactionIssueFields.has("lampSampleBufferType")}
              value={value("lampSampleBufferType") || "none"}
              onChange={(e) => onChange("lampSampleBufferType", e.target.value)}
              className="mt-1 h-9 w-full rounded-lg border bg-surface-wash/35 px-2 text-sm"
            >
              <option value="none">None / unspecified</option>
              <option value="water">Water</option>
              <option value="te">TE</option>
              <option value="other-buffered">Other buffered</option>
              <option value="chelating-other">Other chelating</option>
            </select>
          </div>
          {(
            [
              ["lampSampleInputPercent", "Sample input (% final)"],
              ["lampSampleBufferPh", "Sample/buffer pH"],
              ["lampSampleBufferPercent", "Buffer (% final)"],
              ["lampTransportMediumPercent", "Transport medium (% final)"],
              ["lampBileSaltMgMl", "Bile salt (mg/mL)"],
              ["lampCaryBlairPercent", "Cary-Blair (% final)"],
              ["lampUpstreamGuanidineMm", "Upstream guanidine (mM)"],
            ] as const
          ).map(([id, label]) => (
            <div key={id}>
              <Label htmlFor={id} className="text-xs">
                {label}
              </Label>
              <Input
                id={id}
                type="number"
                step="any"
                min={0}
                aria-invalid={reactionIssueFields.has(id)}
                value={value(id)}
                onChange={(e) => onChange(id, e.target.value)}
              />
            </div>
          ))}
        </div>
      </details>
      <div className="rounded-lg border border-border/50 bg-surface-wash/20 p-3">
        <h4 className="text-sm font-medium">Resolved numeric recipe · source-conditioned</h4>
        {Object.keys(numericPreview.values).length ? (
          <div className="mt-2 grid gap-1 text-xs sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(numericPreview.values)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([key, n]) => (
                <div key={key}>
                  <span className="font-mono">{key}</span>:{" "}
                  <strong>{Number.isInteger(n) ? n : Number(n.toFixed(4))}</strong>{" "}
                  <span className="text-muted-foreground">
                    · {numericPreview.origins[key] ?? "resolved"}
                  </span>
                </div>
              ))}
          </div>
        ) : (
          <p className="mt-2 text-xs text-muted-foreground">
            No transferable public numeric baseline is asserted for this current selection.
          </p>
        )}
        {Object.keys(numericPreview.ranges).length ? (
          <p className="mt-2 text-xs text-muted-foreground">
            Reviewed ranges:{" "}
            {Object.entries(numericPreview.ranges)
              .map(([k, r]) => `${k} ${r[0]}–${r[1]}`)
              .join(" · ")}
          </p>
        ) : null}
        {numericPreview.unresolved.length ? (
          <div className="mt-2 rounded border border-warning/35 bg-warning/5 p-2 text-xs text-warning">
            <strong>Unresolved numeric dependencies:</strong>{" "}
            {numericPreview.unresolved.map((x) => x.note).join(" · ")}
          </div>
        ) : null}
        <p className="mt-2 text-xs text-muted-foreground">
          Chemistry resolution has <code>sequence_decision_impact=none</code>; it never silently
          re-ranks primer sequences.
        </p>
      </div>
      <details className="rounded-lg border border-border/50 p-3">
        <summary className="min-h-6 cursor-pointer py-1 text-sm font-medium">
          Source-bounded bench optimization
        </summary>
        <p className="mt-2 text-xs text-muted-foreground">
          Only parameters with an explicit reviewed envelope in the selected protocol are editable.
          Disabled parameters have no source-backed override authority and preserve the named
          protocol.
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          {LAMP_BENCH_FIELD_MAP.map(([field, key, label]) => {
            const range = lampBenchOptimizationRange(protocol, key);
            return (
              <div key={field}>
                <Label htmlFor={field} className="text-xs">
                  {label}
                  {range ? ` · ${range[0]}–${range[1]}` : ""}
                </Label>
                <Input
                  id={field}
                  aria-invalid={reactionIssueFields.has(field)}
                  type="number"
                  step="any"
                  min={range?.[0]}
                  max={range?.[1]}
                  disabled={!range}
                  placeholder={range ? `${range[0]}–${range[1]}` : "No reviewed override"}
                  value={value(field)}
                  onChange={(e) => onChange(field, e.target.value)}
                />
              </div>
            );
          })}
        </div>
      </details>
      {reactionScenarioIssues.length ? (
        <div
          role="alert"
          className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-xs text-destructive"
        >
          <p className="font-medium">Resolve these LAMP scenario conflicts before Run:</p>
          <ul className="mt-1 list-disc space-y-1 pl-4">
            {Array.from(new Set(reactionScenarioIssues.map((issue) => issue.message))).map(
              (message) => (
                <li key={message}>{message}</li>
              ),
            )}
          </ul>
        </div>
      ) : null}
      {pyrophosphataseProtocol ? (
        <p className="text-xs text-muted-foreground">
          The selected chemistry contains inorganic pyrophosphatase; pyrophosphate-turbidity
          detection is hard-incompatible.
        </p>
      ) : null}
      {m1712 ? (
        <p className="text-xs text-muted-foreground">
          NEB recommends calcein or Eriochrome Black T for M1712 metal-indicator readout; HNB is
          disabled because reviewed guidance reports poor contrast.
        </p>
      ) : null}
    </div>
  );
}

export function LampTargetFields({
  value,
  onChange,
}: {
  value: (key: string) => string;
  onChange: (key: string, next: string) => void;
}) {
  return (
    <div className="space-y-3 rounded-lg border border-border/60 bg-surface-wash/25 p-4">
      <div>
        <h3 className="font-serif text-base font-semibold">LAMP target context</h3>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          Target topology is biological input. The six-region geometry, inner-primer linker and
          search windows are configured on the dedicated LAMP Design page so they are not mixed with
          sequence identity or reaction chemistry.
        </p>
      </div>
      <div>
        <Label htmlFor="lampCircular" className="text-xs">
          Target topology
        </Label>
        <select
          id="lampCircular"
          name="circular"
          value={value("circular") || "false"}
          onChange={(event) => onChange("circular", event.target.value)}
          className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none sm:max-w-sm"
        >
          <option value="false">Linear target · Gen-1 qualified topology</option>
        </select>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          Gen-1 LAMP is qualified for an explicitly linear representation. Circular input remains
          fail-closed because an origin-spanning six-region locus cannot be inferred safely from a
          linearized sequence.
        </p>
      </div>
    </div>
  );
}

/**
 * Which PrimerExplorer V5 parameter set to use.
 *
 * Empty means the source-backed V5 Automatic Judgment: whole-target GC selects
 * AT-rich at <=45%, GC-rich at ≥60%, otherwise Normal. An explicit choice is a
 * deliberate override and is reported as such.
 */
export function LoopFields({
  value,
  onChange,
}: {
  value: (key: string) => string;
  onChange: (key: string, next: string) => void;
}) {
  const lampGeometryProfile = value("lampGeometryProfile") || "primerexplorer-v5-compat";
  const evidenceGeometry = lampGeometryProfile === "pcrstudio-evidence-2026";
  const outerGapLabel = evidenceGeometry ? "F2–F3 / B2–B3 gap 0–60" : "F2–F3 / B2–B3 gap 0–20";

  return (
    <div className="space-y-3 rounded-lg border border-border/60 bg-surface-wash/25 p-4">
      <div>
        <h3 className="font-serif text-base font-semibold">Which window set</h3>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          Leave this on Automatic Judgment to reproduce PrimerExplorer V5&apos;s published
          whole-target GC selection (AT-rich ≤45%, GC-rich ≥60%, otherwise Normal), or override it
          explicitly when a reviewed design protocol requires a named branch.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <div>
          <Label htmlFor="lampDesignIntent" className="text-xs">
            Design intent
          </Label>
          <select
            id="lampDesignIntent"
            value={value("lampDesignIntent") || "standard"}
            onChange={(e) => onChange("lampDesignIntent", e.target.value)}
            className="mt-1 h-9 w-full rounded-lg border bg-surface-wash/35 px-2 text-sm"
          >
            <option value="standard">Standard target-centred design</option>
            <option value="panel-conservation-aware">
              Panel conservation-aware · MAFFT required
            </option>
            <option value="mutation-anchored-specific">
              Mutation-anchored specific · empirical validation required
            </option>
            <option value="fixed-primer-anchor">Fixed-primer anchor · exact oligos</option>
          </select>
        </div>
        <div>
          <Label htmlFor="lampDesignStage" className="text-xs">
            Design stage
          </Label>
          <select
            id="lampDesignStage"
            value={value("lampDesignStage") || "integrated"}
            onChange={(e) => onChange("lampDesignStage", e.target.value)}
            className="mt-1 h-9 w-full rounded-lg border bg-surface-wash/35 px-2 text-sm"
          >
            {LAMP_DESIGN_STAGES.map((stage) => (
              <option key={stage} value={stage}>
                {stage === "integrated"
                  ? "Integrated core + loops"
                  : stage === "core-first"
                    ? "Stage 1 · core four only"
                    : "Stage 2 · add loops to fixed core"}
              </option>
            ))}
          </select>
        </div>
        <div>
          <Label htmlFor="lampLoopPolicy" className="text-xs">
            Loop-primer architecture
          </Label>
          <select
            id="lampLoopPolicy"
            value={value("lampLoopPolicy") || "prefer-six"}
            onChange={(e) => onChange("lampLoopPolicy", e.target.value)}
            disabled={["core-first", "add-loops"].includes(value("lampDesignStage"))}
            className="mt-1 h-9 w-full rounded-lg border bg-surface-wash/35 px-2 text-sm disabled:opacity-60"
          >
            <option value="prefer-six">Prefer six-primer sets</option>
            <option value="require-six">Require LF + LB</option>
            <option value="core-four-only">Core four primers only</option>
          </select>
        </div>
      </div>
      {value("lampDesignIntent") === "fixed-primer-anchor" ? (
        <fieldset className="grid gap-2 rounded-lg border border-border/60 p-3 sm:grid-cols-3">
          <legend className="px-1 text-xs font-medium">Exact fixed LAMP oligos</legend>
          {(["F3", "B3", "FIP", "BIP", "LF", "LB"] as const).map((role) => (
            <div key={role}>
              <Label htmlFor={`lampFixed${role}`} className="text-xs">
                {role}
                {["F3", "B3", "FIP", "BIP"].includes(role) &&
                value("lampDesignStage") === "add-loops"
                  ? " · required"
                  : ""}
              </Label>
              <Input
                id={`lampFixed${role}`}
                value={value(`lampFixed${role}`)}
                onChange={(e) => onChange(`lampFixed${role}`, e.target.value.toUpperCase())}
                placeholder="ACGT…"
                className="mt-1 font-mono text-xs"
              />
            </div>
          ))}
        </fieldset>
      ) : null}
      {value("lampDesignIntent") === "mutation-anchored-specific" ? (
        <fieldset className="grid gap-2 rounded-lg border border-border/60 p-3 sm:grid-cols-4">
          <legend className="px-1 text-xs font-medium">Allele-specific positional anchor</legend>
          <div>
            <Label htmlFor="lampVariantPosition" className="text-xs">
              0-based position
            </Label>
            <Input
              id="lampVariantPosition"
              inputMode="numeric"
              value={value("lampVariantPosition")}
              onChange={(e) => onChange("lampVariantPosition", e.target.value)}
              className="mt-1"
            />
          </div>
          <div>
            <Label htmlFor="lampVariantRef" className="text-xs">
              REF
            </Label>
            <Input
              id="lampVariantRef"
              maxLength={1}
              value={value("lampVariantRef")}
              onChange={(e) => onChange("lampVariantRef", e.target.value.toUpperCase())}
              className="mt-1 font-mono"
            />
          </div>
          <div>
            <Label htmlFor="lampVariantAlt" className="text-xs">
              ALT in submitted template
            </Label>
            <Input
              id="lampVariantAlt"
              maxLength={1}
              value={value("lampVariantAlt")}
              onChange={(e) => onChange("lampVariantAlt", e.target.value.toUpperCase())}
              className="mt-1 font-mono"
            />
          </div>
          <div>
            <Label htmlFor="lampVariantAnchor" className="text-xs">
              Primer-end anchor
            </Label>
            <select
              id="lampVariantAnchor"
              value={value("lampVariantAnchor") || LAMP_MUTATION_ANCHORS[0]}
              onChange={(e) => onChange("lampVariantAnchor", e.target.value)}
              className="mt-1 h-9 w-full rounded-lg border bg-surface-wash/35 px-2 text-xs"
            >
              {LAMP_MUTATION_ANCHORS.map((anchor) => (
                <option key={anchor} value={anchor}>
                  {anchor}
                </option>
              ))}
            </select>
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground sm:col-span-4">
            PCRStudio constrains variant placement only. It does not invent a universal secondary
            mismatch or claim allele discrimination without paired WT/MUT empirical validation.
          </p>
        </fieldset>
      ) : null}

      <div className="space-y-1.5">
        <Label htmlFor="parameterSet" className="text-xs">
          PrimerExplorer parameter set
        </Label>
        <select
          id="parameterSet"
          value={value("parameterSet")}
          onChange={(event) => onChange("parameterSet", event.target.value)}
          className="h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none sm:max-w-sm"
        >
          <option value="">Automatic Judgment — PrimerExplorer V5</option>
          <option value="normal">Balanced target</option>
          <option value="at-rich">AT-rich target</option>
          <option value="gc-rich">GC-rich target</option>
        </select>
      </div>

      <div className="grid gap-3 border-t pt-3 sm:grid-cols-2">
        <div>
          <Label htmlFor="lampGeometryProfile" className="text-xs">
            Geometry profile
          </Label>
          <select
            id="lampGeometryProfile"
            value={value("lampGeometryProfile") || "primerexplorer-v5-compat"}
            onChange={(event) => onChange("lampGeometryProfile", event.target.value)}
            className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <option value="primerexplorer-v5-compat">PrimerExplorer V5 public-rule profile</option>
            <option value="pcrstudio-evidence-2026">PCRStudio Evidence 2026</option>
          </select>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            Evidence 2026 is an explicit multi-source geometry profile: outer-gap eligibility is
            0–60 bases with 40–60 preferred, and F2–B2 has a soft preference band. NEB loop-Tm
            guidance is documented but is not applied on the V5 Tm scale until a matching versioned
            thermodynamic model exists. It is not a proprietary-tool clone.
          </p>
        </div>
        <div>
          <Label htmlFor="lampInnerLinker" className="text-xs">
            FIP/BIP junction
          </Label>
          <select
            id="lampInnerLinker"
            value={value("lampInnerLinker") || "none"}
            onChange={(event) => onChange("lampInnerLinker", event.target.value)}
            className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <option value="none">No synthetic linker</option>
            <option value="tttt">TTTT linker</option>
          </select>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            TTTT is a tested LAMP inner-primer variant, not a universal performance rule.
            Whole-oligo structure calculations include the selected linker.
          </p>
        </div>
      </div>

      <p className="text-xs leading-relaxed text-muted-foreground">
        LAMP uses four core oligos (F3, B3, FIP and BIP) and may add LF/LB, so a complete set has
        four to six ordered primers. The geometry must place the six core target regions in order;
        loop-primer sites are optional. Fluorescence, colour and turbidity are chemistry/readout
        choices, not interchangeable evidence of specificity.
      </p>

      {/*
       * Behind a disclosure, because the three sets are the right answer for
       * almost everybody and a page that opens on six empty number boxes
       * suggests they are not. What is behind it is real: a target AT-rich in
       * one half and GC-rich in the other fits none of the three, and until
       * this the only control was which of three.
       */}
      <details className="border-t pt-3">
        <summary className="min-h-6 cursor-pointer py-1 text-xs text-muted-foreground hover:text-foreground">
          Set the windows yourself
        </summary>

        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
          Empty means the selected set above. Anything you fill in is yours rather than the
          published set&rsquo;s, and the result says which. These are thermodynamic/search windows,
          not an automatically generated bench hold.
        </p>

        <div className="mt-3 space-y-3">
          {(
            [
              ["outer", "F3, F2, B2, B3 — the ones that prime on the template"],
              ["inner", "F1c and B1c — the stems, which fold back rather than priming"],
              ["loop", "LF and LB, if the set uses them"],
            ] as const
          ).map(([role, what]) => (
            <div key={role} className="space-y-1.5">
              <h4 className="text-xs font-medium capitalize">{role}</h4>
              <p className="text-xs leading-relaxed text-muted-foreground">{what}</p>
              <div className="grid gap-2 sm:grid-cols-4">
                {(
                  [
                    ["tm_min", "coolest °C"],
                    ["tm_max", "warmest °C"],
                    ["length_min", "shortest nt"],
                    ["length_max", "longest nt"],
                  ] as const
                ).map(([field, label]) => (
                  <Input
                    aria-label={`${role} ${label}`}
                    key={field}
                    type="number"
                    value={value(`w_${role}_${field}`)}
                    onChange={(event) => onChange(`w_${role}_${field}`, event.target.value)}
                    placeholder={label}
                  />
                ))}
              </div>
            </div>
          ))}

          <div className="space-y-1.5">
            <h4 className="text-xs font-medium">The geometry</h4>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {(
                [
                  ["f2_b2_span", "F2–B2 amplified region 120–180"],
                  ["loop_span", "loop span 40–60"],
                  ["outer_gap", outerGapLabel],
                  ["middle_gap", "F1c–B1c gap 0–100"],
                ] as const
              ).map(([field, label]) => (
                <div key={field} className="grid grid-cols-2 gap-1">
                  <Input
                    type="number"
                    aria-label={`${label} shortest`}
                    value={value(`w_${field}_min`)}
                    onChange={(event) => onChange(`w_${field}_min`, event.target.value)}
                    placeholder="from"
                  />
                  <Input
                    type="number"
                    aria-label={`${label} longest`}
                    value={value(`w_${field}_max`)}
                    onChange={(event) => onChange(`w_${field}_max`, event.target.value)}
                    placeholder="to"
                  />
                </div>
              ))}
            </div>
            <p className="text-xs leading-relaxed text-muted-foreground">
              {evidenceGeometry ? (
                <>
                  Evidence 2026 keeps the same coordinate definitions but uses an F2–F3/B2–B3
                  eligibility interval of 0–60 nt and softly prefers 40–60 nt. F2–B2 remains a
                  distinct amplified-region constraint, while F1c–B1c is the inner middle gap. These
                  are source-scoped search rules, not a wet-lab success guarantee.
                </>
              ) : (
                <>
                  Geometry follows PrimerExplorer V5 definitions: F2–B2 includes both primer
                  regions, Loop(F1c–F2) is 40–60 nt including F2/B2, F2–F3 excludes the primer
                  regions and is 0–20 nt, and F1c–B1c excludes the primer regions and is 0–100 nt.
                  The full F3–B3 envelope is reported separately and is not used as the
                  amplified-region gate.
                </>
              )}
            </p>
          </div>
        </div>
      </details>
    </div>
  );
}

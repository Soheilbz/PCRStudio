"use client";

import { useState } from "react";

import { WrappedField } from "@/components/form-parts";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { StepPlan } from "@/components/design/page-plan";
import type { RawDraftValues } from "@/lib/projects/draft";
import { Step } from "@/components/project/workspace-parts";
import { parseEvidenceFile, type EvidenceImportKind } from "@/lib/evidence-import";

type Draft = RawDraftValues;

function text(draft: Draft, key: string): string {
  return draft[key] ?? "";
}

export function ValidationEvidenceStep({
  draft,
  set,
  words,
  moduleId,
}: {
  draft: Draft;
  set: (key: string, value: string) => void;
  words: StepPlan;
  moduleId: string;
}) {
  const note = (
    <p className="rounded-lg border border-dashed border-border/60 bg-surface-wash/20 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
      These fields are experimental-evidence/provenance records. They do not silently alter Primer3,
      MFEprimer, BLAST, LAMP topology or candidate ranking. Missing evidence is reported as missing;
      it is never synthesized from an in-silico score.
    </p>
  );

  if (moduleId === "tetra-primer-arms") {
    const minimum = Number(text(draft, "tetraMinBandSeparationBp"));
    return (
      <Step title={words.heading} description={words.description}>
        <div className="space-y-3 rounded-lg border border-border/60 bg-surface-wash/25 p-3">
          <WrappedField
            label="Minimum band-size separation your validated readout can resolve (bp)"
            hint="Required assay/readout evidence. PCRStudio compares predicted diagnostic products to this declared capability and does not invent a universal agarose threshold."
          >
            <Input
              type="number"
              min={1}
              required
              value={text(draft, "tetraMinBandSeparationBp")}
              onChange={(event) => set("tetraMinBandSeparationBp", event.target.value)}
              placeholder="Enter validated gel/capillary resolution"
              className="sm:max-w-sm"
            />
          </WrappedField>
          <p className="text-xs leading-relaxed text-muted-foreground">
            {Number.isFinite(minimum) && minimum > 0
              ? `Current declared minimum resolvable separation: ${minimum} bp.`
              : "No readout-resolution authority has been recorded yet."}{" "}
            This requirement affects whether a three-band tetra-ARMS result is interpretable; it
            does not change the variant identity or silently retune primer thermodynamics.
          </p>
        </div>
      </Step>
    );
  }

  if (moduleId === "qpcr-sybr") {
    const slope = Number(text(draft, "qpcrStandardCurveSlope"));
    const calculatedEfficiency =
      Number.isFinite(slope) && slope < 0 ? (Math.pow(10, -1 / slope) - 1) * 100 : null;
    const fromRna = text(draft, "fromRna") === "true";
    const qpcrCoverage = [
      [
        "standard-curve slope or measured efficiency",
        Boolean(text(draft, "qpcrStandardCurveSlope") || text(draft, "qpcrEfficiencyPercent")),
      ],
      ["standard-curve R²", Boolean(text(draft, "qpcrStandardCurveR2"))],
      [
        "NTC status",
        Boolean(text(draft, "qpcrNtcStatus") && text(draft, "qpcrNtcStatus") !== "unresolved"),
      ],
      ...(fromRna
        ? [
            [
              "No-RT control status",
              Boolean(
                text(draft, "qpcrNoRtStatus") && text(draft, "qpcrNoRtStatus") !== "unresolved",
              ),
            ] as [string, boolean],
          ]
        : []),
      ["melt evidence", Boolean(text(draft, "qpcrMeltEvidence"))],
      ["replicate / matrix / validation notes", Boolean(text(draft, "qpcrValidationNotes"))],
    ] as Array<[string, boolean]>;
    return (
      <Step title={words.heading} description={words.description}>
        {note}
        <EvidenceImporter kind="qpcr-sybr" set={set} />
        <div className="grid gap-3 sm:grid-cols-3">
          <WrappedField
            label="Standard-curve slope"
            hint="If supplied, PCRStudio derives amplification efficiency from the conventional 10^(-1/slope)-1 relationship."
          >
            <Input
              value={text(draft, "qpcrStandardCurveSlope")}
              onChange={(e) => set("qpcrStandardCurveSlope", e.target.value)}
              inputMode="decimal"
              placeholder="-3.32"
            />
          </WrappedField>
          <WrappedField
            label="R²"
            hint="Measured standard-curve linearity; not inferred from primer sequence."
          >
            <Input
              value={text(draft, "qpcrStandardCurveR2")}
              onChange={(e) => set("qpcrStandardCurveR2", e.target.value)}
              inputMode="decimal"
              placeholder="0.998"
            />
          </WrappedField>
          <WrappedField
            label="Efficiency (%)"
            hint={
              calculatedEfficiency === null
                ? "Enter a measured/reported value or provide slope for a derived value."
                : `Slope-derived efficiency: ${calculatedEfficiency.toFixed(1)}%.`
            }
          >
            <Input
              value={text(draft, "qpcrEfficiencyPercent")}
              onChange={(e) => set("qpcrEfficiencyPercent", e.target.value)}
              inputMode="decimal"
              placeholder={calculatedEfficiency === null ? "95" : calculatedEfficiency.toFixed(1)}
            />
          </WrappedField>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <EvidenceChoice
            label="NTC"
            value={text(draft, "qpcrNtcStatus")}
            set={(v) => set("qpcrNtcStatus", v)}
          />
          <EvidenceChoice
            label="No-RT control"
            value={text(draft, "qpcrNoRtStatus")}
            set={(v) => set("qpcrNoRtStatus", v)}
          />
          <WrappedField
            label="Melt peaks"
            hint="Record observed peak count/temperatures or a concise interpretation."
          >
            <Input
              value={text(draft, "qpcrMeltEvidence")}
              onChange={(e) => set("qpcrMeltEvidence", e.target.value)}
              placeholder="single peak at 82.4 °C"
            />
          </WrappedField>
        </div>
        <div className="grid gap-3 sm:grid-cols-4">
          <NumberEvidence label="LoD" field="qpcrLod" draft={draft} set={set} />
          <NumberEvidence label="LLOQ" field="qpcrLloq" draft={draft} set={set} />
          <NumberEvidence label="ULOQ" field="qpcrUloq" draft={draft} set={set} />
          <NumberEvidence label="Replicates" field="qpcrReplicates" draft={draft} set={set} />
          <NumberEvidence label="Mean Cq" field="qpcrCqMean" draft={draft} set={set} />
          <NumberEvidence
            label="Dynamic range (logs)"
            field="qpcrDynamicRangeLogs"
            draft={draft}
            set={set}
          />
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <TextEvidence label="Instrument" field="qpcrInstrument" draft={draft} set={set} />
          <TextEvidence
            label="Software/version"
            field="qpcrSoftwareVersion"
            draft={draft}
            set={set}
          />
          <TextEvidence
            label="Baseline method"
            field="qpcrBaselineMethod"
            draft={draft}
            set={set}
          />
          <TextEvidence
            label="Threshold/Cq method"
            field="qpcrThresholdMethod"
            draft={draft}
            set={set}
          />
          <TextEvidence
            label="Positive-control status"
            field="qpcrPositiveControlStatus"
            draft={draft}
            set={set}
          />
          <TextEvidence
            label="Raw-data / RDES / RDML reference"
            field="qpcrRawDataReference"
            draft={draft}
            set={set}
          />
          <TextEvidence
            label="Reference genes"
            field="qpcrReferenceGenes"
            draft={draft}
            set={set}
          />
          <TextEvidence
            label="Normalization method"
            field="qpcrNormalizationMethod"
            draft={draft}
            set={set}
          />
          <TextEvidence
            label="Inhibition assessment"
            field="qpcrInhibitionAssessment"
            draft={draft}
            set={set}
          />
        </div>
        <WrappedField
          label="Replicate / validation notes"
          hint="Record replicate dispersion, standard-curve dilution series, sample matrix and any protocol-specific evidence needed to interpret the numbers."
        >
          <Textarea
            value={text(draft, "qpcrValidationNotes")}
            onChange={(e) => set("qpcrValidationNotes", e.target.value)}
            rows={4}
          />
        </WrappedField>
        <EvidenceCoverage
          title="Selected MIQE 2.0 evidence coverage"
          items={qpcrCoverage}
          boundary="This is a PCRStudio completeness check for the evidence fields exposed on this page, not a claim of full MIQE 2.0 compliance. Sample handling, extraction, calibration, reporting and other MIQE requirements remain experiment-specific."
        />
      </Step>
    );
  }

  if (moduleId === "digital-pcr") {
    const accepted = Number(text(draft, "dpcrAcceptedPartitions"));
    const negative = Number(text(draft, "dpcrNegativePartitions"));
    const positive = Number(text(draft, "dpcrPositivePartitions"));
    const volume = Number(text(draft, "dpcrPartitionVolumeUl"));
    const dilution = Number(text(draft, "dpcrDilutionFactor") || "1");
    const lambda =
      accepted > 0 && negative > 0 && negative <= accepted ? -Math.log(negative / accepted) : null;
    const copiesPerUl =
      lambda !== null && volume > 0 ? (lambda / volume) * (dilution > 0 ? dilution : 1) : null;
    // A transparent binomial interval for the negative-partition fraction,
    // transformed through lambda = -ln(p0). This is deliberately not labelled
    // as a platform-qualified dPCR confidence interval: instrument software can
    // apply additional accepted-partition, volume and cluster-model rules.
    const z95 = 1.959963984540054;
    const negativeFraction =
      accepted > 0 && negative >= 0 && negative <= accepted ? negative / accepted : null;
    const wilson =
      negativeFraction !== null
        ? (() => {
            const z2 = z95 * z95;
            const denominator = 1 + z2 / accepted;
            const centre = (negativeFraction + z2 / (2 * accepted)) / denominator;
            const half =
              (z95 / denominator) *
              Math.sqrt(
                (negativeFraction * (1 - negativeFraction)) / accepted +
                  z2 / (4 * accepted * accepted),
              );
            return [Math.max(0, centre - half), Math.min(1, centre + half)] as const;
          })()
        : null;
    const lambdaCi =
      wilson && wilson[0] > 0 && wilson[1] > 0
        ? ([-Math.log(wilson[1]), -Math.log(wilson[0])] as const)
        : null;
    const concentrationCi =
      lambdaCi && volume > 0
        ? ([
            (lambdaCi[0] / volume) * (dilution > 0 ? dilution : 1),
            (lambdaCi[1] / volume) * (dilution > 0 ? dilution : 1),
          ] as const)
        : null;
    const dpcrCoverage: Array<[string, boolean]> = [
      ["accepted partition count", Boolean(text(draft, "dpcrAcceptedPartitions"))],
      [
        "positive and negative partition counts",
        Boolean(text(draft, "dpcrPositivePartitions") && text(draft, "dpcrNegativePartitions")),
      ],
      ["threshold method", Boolean(text(draft, "dpcrThresholdMethod"))],
      ["partition volume authority/value", Boolean(text(draft, "dpcrPartitionVolumeUl"))],
      ["controls / run-QC / software notes", Boolean(text(draft, "dpcrValidationNotes"))],
    ];
    return (
      <Step title={words.heading} description={words.description}>
        {note}
        <EvidenceImporter kind="digital-pcr" set={set} />
        <div className="grid gap-3 sm:grid-cols-4">
          <NumberEvidence
            label="Total partitions"
            field="dpcrTotalPartitions"
            draft={draft}
            set={set}
          />
          <NumberEvidence
            label="Accepted partitions"
            field="dpcrAcceptedPartitions"
            draft={draft}
            set={set}
          />
          <NumberEvidence
            label="Positive partitions"
            field="dpcrPositivePartitions"
            draft={draft}
            set={set}
          />
          <NumberEvidence
            label="Negative partitions"
            field="dpcrNegativePartitions"
            draft={draft}
            set={set}
          />
        </div>
        {accepted > 0 && positive >= 0 && negative >= 0 && positive + negative > accepted ? (
          <p className="text-xs text-destructive">
            Positive + negative partitions cannot exceed accepted partitions; review rain/ambiguous
            handling.
          </p>
        ) : null}
        <div className="grid gap-3 sm:grid-cols-4">
          <NumberEvidence
            label="Rain / ambiguous"
            field="dpcrRainPartitions"
            draft={draft}
            set={set}
          />
          <WrappedField
            label="Threshold method"
            hint="Manual, software automatic, control-derived, cluster model, or another explicitly documented method."
          >
            <Input
              value={text(draft, "dpcrThresholdMethod")}
              onChange={(e) => set("dpcrThresholdMethod", e.target.value)}
              placeholder="control-derived manual threshold"
            />
          </WrappedField>
          <WrappedField
            label="Partition volume (µL)"
            hint="Use only a platform/software authority applicable to the run; PCRStudio does not invent volume from instrument name."
          >
            <Input
              value={text(draft, "dpcrPartitionVolumeUl")}
              onChange={(e) => set("dpcrPartitionVolumeUl", e.target.value)}
              inputMode="decimal"
            />
          </WrappedField>
          <WrappedField
            label="Dilution factor"
            hint="Applied only to the optional displayed concentration calculation."
          >
            <Input
              value={text(draft, "dpcrDilutionFactor") || "1"}
              onChange={(e) => set("dpcrDilutionFactor", e.target.value)}
              inputMode="decimal"
            />
          </WrappedField>
        </div>
        {accepted > 0 && negative === 0 ? (
          <p className="rounded-lg border border-warning/35 bg-warning/5 px-3 py-2 text-xs leading-relaxed text-warning">
            No accepted negative partitions were entered, so λ has no finite maximum-likelihood
            estimate. Treat this run as saturated for this simple calculation and use the
            platform-qualified dilution/analysis workflow.
          </p>
        ) : null}
        {lambda !== null ? (
          <div className="rounded-lg border bg-surface-wash/30 p-3 text-xs leading-relaxed">
            <strong>Poisson occupancy λ:</strong> {lambda.toFixed(4)} copies/partition.
            {lambdaCi ? (
              <>
                {" "}
                <strong> Approx. 95% occupancy interval:</strong> {lambdaCi[0].toFixed(4)}–
                {lambdaCi[1].toFixed(4)}.
              </>
            ) : null}
            {copiesPerUl !== null ? (
              <>
                {" "}
                <strong> Volume-normalized estimate:</strong> {copiesPerUl.toFixed(3)} copies/µL
                after the stated dilution factor.
              </>
            ) : null}
            {concentrationCi ? (
              <>
                {" "}
                <strong> Approx. 95% concentration interval:</strong>{" "}
                {concentrationCi[0].toFixed(3)}–{concentrationCi[1].toFixed(3)} copies/µL.
              </>
            ) : null}
            <div className="mt-1 text-xs text-muted-foreground">
              The interval is a transparent Wilson-binomial interval for the entered
              negative-partition fraction transformed through λ = −ln(p₀). It is an analytical aid,
              not a substitute for the selected platform/software&apos;s qualified partition-volume,
              threshold, rain/cluster and confidence-interval method.
            </div>
          </div>
        ) : null}
        <WrappedField
          label="Controls and run-QC notes"
          hint="Record NTC/positive controls, rain policy, software version, threshold review and any excluded wells/partitions."
        >
          <Textarea
            value={text(draft, "dpcrValidationNotes")}
            onChange={(e) => set("dpcrValidationNotes", e.target.value)}
            rows={4}
          />
        </WrappedField>
        <EvidenceCoverage
          title="Selected dMIQE run-evidence coverage"
          items={dpcrCoverage}
          boundary="This checks only the run-evidence fields PCRStudio exposes here. It is not full dMIQE compliance and it does not replace platform-qualified partition-volume, threshold, cluster, control or uncertainty analysis."
        />
      </Step>
    );
  }

  if (moduleId === "rpa") {
    return (
      <Step title={words.heading} description={words.description}>
        {note}
        <div className="grid gap-3 sm:grid-cols-3">
          <NumberEvidence
            label="Candidate pairs to screen"
            field="rpaScreenCandidateCount"
            draft={draft}
            set={set}
            placeholder="12"
          />
          <NumberEvidence
            label="Replicates per candidate"
            field="rpaScreenReplicates"
            draft={draft}
            set={set}
            placeholder="3"
          />
          <WrappedField
            label="Measured response"
            hint="For example time-to-positive, endpoint fluorescence or lateral-flow band intensity."
          >
            <Input
              value={text(draft, "rpaScreenResponse")}
              onChange={(e) => set("rpaScreenResponse", e.target.value)}
              placeholder="time-to-positive"
            />
          </WrappedField>
        </div>
        <WrappedField
          label="Controls / input levels"
          hint="Define target inputs, NTCs, relevant non-targets and any positive control before screening candidates."
        >
          <Textarea
            value={text(draft, "rpaScreenControls")}
            onChange={(e) => set("rpaScreenControls", e.target.value)}
            rows={3}
          />
        </WrappedField>
        <WrappedField
          label="Selection rule and observed outcomes"
          hint="Record why a candidate was retained. PCRStudio does not infer a universal RPA performance score from sequence thermodynamics."
        >
          <Textarea
            value={text(draft, "rpaScreenNotes")}
            onChange={(e) => set("rpaScreenNotes", e.target.value)}
            rows={4}
          />
        </WrappedField>
      </Step>
    );
  }

  if (moduleId === "lamp") {
    return (
      <Step title={words.heading} description={words.description}>
        {note}
        <div className="grid gap-3 sm:grid-cols-3">
          <NumberEvidence
            label="Complete sets to screen"
            field="lampValidationSetCount"
            draft={draft}
            set={set}
            placeholder="4"
          />
          <NumberEvidence
            label="Replicates per set"
            field="lampValidationReplicates"
            draft={draft}
            set={set}
            placeholder="3"
          />
          <WrappedField
            label="Measured response"
            hint="Time-to-positive, endpoint fluorescence/colour/turbidity, or another named readout owned by the selected chemistry."
          >
            <Input
              value={text(draft, "lampValidationResponse")}
              onChange={(e) => set("lampValidationResponse", e.target.value)}
              placeholder="time-to-positive"
            />
          </WrappedField>
        </div>
        <WrappedField
          label="Target input / LoD plan"
          hint="Record input series, matrix and how detection probability or an operational LoD will be assessed."
        >
          <Textarea
            value={text(draft, "lampValidationInputs")}
            onChange={(e) => set("lampValidationInputs", e.target.value)}
            rows={3}
          />
        </WrappedField>
        <div className="grid gap-3 sm:grid-cols-2">
          <EvidenceChoice
            label="NTC / non-template amplification"
            value={text(draft, "lampNtcStatus")}
            set={(v) => set("lampNtcStatus", v)}
          />
          <EvidenceChoice
            label="Positive control"
            value={text(draft, "lampPositiveControlStatus")}
            set={(v) => set("lampPositiveControlStatus", v)}
          />
          <EvidenceChoice
            label="No-RT control · RNA workflows"
            value={text(draft, "lampNoRtStatus")}
            set={(v) => set("lampNoRtStatus", v)}
          />
          <WrappedField
            label="Observed LoD / screening summary"
            hint="Only measured evidence belongs here; leave unresolved when no bench experiment has been performed."
          >
            <Input
              value={text(draft, "lampObservedLod")}
              onChange={(e) => set("lampObservedLod", e.target.value)}
              placeholder="unresolved / 50 copies per reaction at stated criterion"
            />
          </WrappedField>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <WrappedField label="Time-to-positive evidence">
            <Input
              value={text(draft, "lampTimeToPositive")}
              onChange={(e) => set("lampTimeToPositive", e.target.value)}
            />
          </WrappedField>
          <WrappedField label="Confirmation peak / curve">
            <Input
              value={text(draft, "lampConfirmationEvidence")}
              onChange={(e) => set("lampConfirmationEvidence", e.target.value)}
            />
          </WrappedField>
          <WrappedField label="Inclusivity evidence">
            <Textarea
              value={text(draft, "lampInclusivityEvidence")}
              onChange={(e) => set("lampInclusivityEvidence", e.target.value)}
              rows={2}
            />
          </WrappedField>
          <WrappedField label="Exclusivity evidence">
            <Textarea
              value={text(draft, "lampExclusivityEvidence")}
              onChange={(e) => set("lampExclusivityEvidence", e.target.value)}
              rows={2}
            />
          </WrappedField>
          <WrappedField label="Matrix spike / inhibition evidence">
            <Textarea
              value={text(draft, "lampMatrixSpikeEvidence")}
              onChange={(e) => set("lampMatrixSpikeEvidence", e.target.value)}
              rows={2}
            />
          </WrappedField>
          <WrappedField label="Within-run reproducibility">
            <Textarea
              value={text(draft, "lampWithinRunEvidence")}
              onChange={(e) => set("lampWithinRunEvidence", e.target.value)}
              rows={2}
            />
          </WrappedField>
          <WrappedField label="Between-run reproducibility">
            <Textarea
              value={text(draft, "lampBetweenRunEvidence")}
              onChange={(e) => set("lampBetweenRunEvidence", e.target.value)}
              rows={2}
            />
          </WrappedField>
          <WrappedField label="Lot / operator / day robustness">
            <Textarea
              value={text(draft, "lampRobustnessEvidence")}
              onChange={(e) => set("lampRobustnessEvidence", e.target.value)}
              rows={2}
            />
          </WrappedField>
          <WrappedField label="Sample-matrix evidence">
            <Textarea
              value={text(draft, "lampSampleMatrixEvidence")}
              onChange={(e) => set("lampSampleMatrixEvidence", e.target.value)}
              rows={2}
            />
          </WrappedField>
        </div>
        <WrappedField
          label="Validation notes"
          hint="Record candidate-set comparison, false-positive behaviour, replicate consistency and selection rationale."
        >
          <Textarea
            value={text(draft, "lampValidationNotes")}
            onChange={(e) => set("lampValidationNotes", e.target.value)}
            rows={4}
          />
        </WrappedField>
      </Step>
    );
  }

  return (
    <Step title={words.heading} description={words.description}>
      {note}
    </Step>
  );
}

export function LampGeometryDiagram() {
  const regions = ["F3", "F2", "F1c", "B1c", "B2", "B3"];
  return (
    <div className="space-y-3 rounded-lg border border-border/70 bg-surface-wash/25 p-3">
      <div>
        <p className="text-sm font-medium">LAMP target geometry</p>
        <p className="text-xs leading-relaxed text-muted-foreground">
          PCRStudio treats these as ordered target regions, not six independent PCR primers. The
          composite inner primers are assembled explicitly from the mapped regions and selected
          linker.
        </p>
      </div>
      <div
        className="grid grid-cols-6 gap-1"
        role="img"
        aria-label="LAMP target-region order: F3, F2, F1c, B1c, B2, B3"
      >
        {regions.map((region) => (
          <div
            key={region}
            className="rounded-md border bg-background px-1 py-2 text-center text-xs font-semibold"
          >
            {region}
          </div>
        ))}
      </div>
      <div className="grid gap-2 text-xs leading-relaxed text-muted-foreground sm:grid-cols-2">
        <div className="rounded-md border border-dashed px-2 py-1.5">
          <strong className="text-foreground">FIP</strong> = F1c + linker + F2
        </div>
        <div className="rounded-md border border-dashed px-2 py-1.5">
          <strong className="text-foreground">BIP</strong> = B1c + linker + B2
        </div>
        <div className="rounded-md border border-dashed px-2 py-1.5">
          <strong className="text-foreground">LF</strong> occupies the F1/F2 loop when a compatible
          loop region exists.
        </div>
        <div className="rounded-md border border-dashed px-2 py-1.5">
          <strong className="text-foreground">LB</strong> occupies the B1/B2 loop when a compatible
          loop region exists.
        </div>
      </div>
    </div>
  );
}

function EvidenceCoverage({
  title,
  items,
  boundary,
}: {
  title: string;
  items: Array<[string, boolean]>;
  boundary: string;
}) {
  const complete = items.filter(([, present]) => present).length;
  const missing = items.filter(([, present]) => !present).map(([label]) => label);
  return (
    <div className="rounded-lg border border-border/70 bg-surface-wash/25 p-3 text-xs leading-relaxed">
      <div className="font-medium">
        {title}: {complete}/{items.length}
      </div>
      {missing.length ? (
        <div className="mt-1 text-muted-foreground">Missing/unresolved: {missing.join(", ")}.</div>
      ) : (
        <div className="mt-1 text-muted-foreground">
          All evidence categories exposed on this page have a recorded value.
        </div>
      )}
      <div className="mt-1 text-xs text-muted-foreground">{boundary}</div>
    </div>
  );
}

function EvidenceChoice({
  label,
  value,
  set,
}: {
  label: string;
  value: string;
  set: (value: string) => void;
}) {
  return (
    <WrappedField
      label={label}
      hint="Measured experimental status; unresolved is a valid state before bench validation."
    >
      <select
        value={value || "unresolved"}
        onChange={(e) => set(e.target.value)}
        className="h-9 w-full rounded-lg border border-border/70 bg-surface-wash/35 px-3 text-sm"
      >
        <option value="unresolved">Unresolved / not measured</option>
        <option value="pass">Pass / no unexpected signal</option>
        <option value="fail">Fail / unexpected signal</option>
        <option value="mixed">Mixed / requires review</option>
      </select>
    </WrappedField>
  );
}

function TextEvidence({
  label,
  field,
  draft,
  set,
}: {
  label: string;
  field: string;
  draft: Draft;
  set: (key: string, value: string) => void;
}) {
  return (
    <WrappedField label={label} hint="Measured/run metadata; leave empty when unavailable.">
      <Input value={text(draft, field)} onChange={(e) => set(field, e.target.value)} />
    </WrappedField>
  );
}

function EvidenceImporter({
  kind,
  set,
}: {
  kind: EvidenceImportKind;
  set: (key: string, value: string) => void;
}) {
  const [status, setStatus] = useState("");
  return (
    <div className="rounded-lg border border-dashed border-border/70 bg-surface-wash/20 p-3 text-xs">
      <label className="font-medium" htmlFor={`evidence-import-${kind}`}>
        Import run-evidence metadata
      </label>
      <input
        id={`evidence-import-${kind}`}
        type="file"
        accept=".csv,.tsv,.txt,.xml,.rdml,.rdes"
        className="mt-2 block w-full text-xs file:mr-3 file:min-h-9 file:rounded-md file:border file:bg-background file:px-3"
        onChange={async (event) => {
          const file = event.target.files?.[0];
          if (!file) return;
          try {
            const parsed = parseEvidenceFile(file.name, await file.text(), kind);
            Object.entries(parsed.fields).forEach(([field, value]) => set(field, value));
            setStatus(
              `${Object.keys(parsed.fields).length} field(s) imported via ${parsed.adapter}.${parsed.warnings.length ? ` ${parsed.warnings.join(" ")}` : ""}`,
            );
          } catch (error) {
            setStatus(error instanceof Error ? error.message : "Evidence import failed.");
          } finally {
            event.target.value = "";
          }
        }}
      />
      <p className="mt-2 text-xs leading-relaxed text-muted-foreground" aria-live="polite">
        {status ||
          "CSV/TSV and RDML/XML/RDES metadata are mapped only to explicit evidence fields. PCRStudio never averages curves, invents thresholds, or infers missing validation values during import."}
      </p>
    </div>
  );
}

function NumberEvidence({
  label,
  field,
  draft,
  set,
  placeholder,
}: {
  label: string;
  field: string;
  draft: Draft;
  set: (key: string, value: string) => void;
  placeholder?: string;
}) {
  return (
    <WrappedField label={label} hint="Measured/run evidence; leave empty when not available.">
      <Input
        type="number"
        min={0}
        value={text(draft, field)}
        onChange={(e) => set(field, e.target.value)}
        placeholder={placeholder}
      />
    </WrappedField>
  );
}

export function SummaryMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border bg-surface-wash/25 p-3">
      <div className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        {label}
      </div>
      <div className="mt-1 text-sm font-medium">{value}</div>
    </div>
  );
}

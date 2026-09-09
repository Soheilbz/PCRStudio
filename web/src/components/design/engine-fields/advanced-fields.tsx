"use client";

import { Label } from "@/components/ui/label";
import { EvidenceInput } from "../evidence-input";

/**
 * The fragments to join, and the chemistry that joins them.
 *
 * Neither has a default. The plan is what this engine takes instead of a
 * template, and the chemistry decides the overlap design contract. The release
 * UI exposes reviewed chemistry identities rather than pretending one overlap
 * rule is portable across Gibson, NEBuilder, In-Fusion and IVA.
 */
export function AssemblyFields({
  section,
  value,
  onChange,
}: {
  section: "design" | "reaction";
  value: (key: string) => string;
  onChange: (key: string, next: string) => void;
}) {
  const method = value("assemblyMethod") || "gibson";
  if (section === "reaction") {
    return (
      <div className="space-y-4 rounded-lg border border-border/60 bg-surface-wash/25 p-4">
        <div>
          <h3 className="font-serif text-base font-semibold">Joining chemistry authority</h3>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            Gibson and NEBuilder HiFi are separate executable branches with separate overlap and
            reaction authorities. Choosing one never re-labels the other.
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <Label htmlFor="assemblyProtocol" className="text-xs">
              Reviewed assembly protocol
            </Label>
            <select
              id="assemblyProtocol"
              required
              value={value("assemblyProtocol")}
              onChange={(e) => onChange("assemblyProtocol", e.target.value)}
              className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
            >
              <option value="">Choose exact protocol</option>
              {method === "gibson" ? (
                <option value="neb-e5510">NEB Gibson Assembly Cloning Kit · E5510</option>
              ) : (
                <>
                  <option value="neb-nebuilder-e2621">NEBuilder HiFi DNA Assembly · E2621</option>
                  <option value="neb-nebuilder-e5520">NEBuilder HiFi DNA Assembly · E5520</option>
                  <option value="neb-nebuilder-e2623">NEBuilder HiFi DNA Assembly · E2623</option>
                </>
              )}
            </select>
          </div>
          <div className="rounded-lg border border-dashed border-border/60 bg-background/35 p-3 text-xs leading-relaxed text-muted-foreground">
            {method === "gibson"
              ? "E5510 owns Gibson overlap/reaction semantics. NEBuilder mismatch-removal and short-fragment behavior are not imported into this branch."
              : "The selected NEBuilder kit owns current overlap/reaction boundaries. Gibson rules are not used as a fallback."}
          </div>
        </div>
        <details className="rounded-lg border border-border/60 bg-background/35 p-3">
          <summary className="cursor-pointer text-xs font-medium">
            Assembly validation evidence
          </summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <EvidenceInput
              id="assemblyInputFragmentCount"
              label="Input fragments"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="assemblyFragmentQc"
              label="Fragment PCR/QC"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="assemblyConcentrationReference"
              label="Concentration reference"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="assemblyMixLot"
              label="Assembly mix / lot"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="assemblyIncubationEvidence"
              label="Incubation evidence"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="assemblyTransformationMethod"
              label="Transformation method"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="assemblyColonyCount"
              label="Colonies"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="assemblyNegativeControlColonies"
              label="Negative-control colonies"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="assemblyColonyPcrEvidence"
              label="Colony-PCR evidence"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="assemblyRestrictionVerification"
              label="Restriction verification"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="assemblyVerifiedCloneCount"
              label="Verified clones"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="assemblySequenceVerification"
              label="Sanger / NGS verification"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="assemblyValidationNotes"
              label="Validation notes"
              value={value}
              onChange={onChange}
            />
          </div>
        </details>
      </div>
    );
  }

  return (
    <div className="space-y-4 rounded-lg border border-border/60 bg-surface-wash/25 p-4">
      <div>
        <h3 className="font-serif text-base font-semibold">Construct graph</h3>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          The ordered fragment list is the construct. Each segment has an explicit production
          method; restriction-generated, synthetic and existing fragments are not treated as PCR
          products simply because they contain sequence.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <Label htmlFor="assemblyMethod" className="text-xs">
            Assembly chemistry
          </Label>
          <select
            id="assemblyMethod"
            required
            value={method}
            onChange={(e) => onChange("assemblyMethod", e.target.value)}
            className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
          >
            <option value="gibson">Gibson Assembly</option>
            <option value="nebuilder">NEBuilder HiFi DNA Assembly</option>
          </select>
        </div>
        <div>
          <Label htmlFor="circular" className="text-xs">
            Finished topology
          </Label>
          <select
            id="circular"
            required
            value={value("circular")}
            onChange={(e) => onChange("circular", e.target.value)}
            className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
          >
            <option value="">Choose finished topology</option>
            <option value="true">Circular — final fragment rejoins the first</option>
            <option value="false">Linear — terminal ends stay open</option>
          </select>
        </div>
      </div>
      <div>
        <Label htmlFor="segments" className="text-xs">
          Ordered fragments
        </Label>
        <textarea
          id="segments"
          required
          value={value("segments")}
          onChange={(e) => onChange("segments", e.target.value)}
          rows={10}
          spellCheck={false}
          placeholder={
            "vector, pcr-amplified, ACGT..., final-construct, 20, 100, 5\ninsert, synthetic-dsdna, TTGC...\n\nOr paste a JSON array for restriction/features/provenance metadata."
          }
          className="mt-1 w-full rounded-lg border-border/70 bg-surface-wash/35 p-2 font-mono text-xs focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        />
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          Compact columns:{" "}
          <code>name, kind, sequence, orientation, concentration_ng/µL, mass_ng, volume_µL</code>.
          For restriction metadata, features and source provenance, paste the typed JSON-array form.
        </p>
      </div>
      <details className="rounded-lg border border-border/60 bg-background/35 p-3">
        <summary className="cursor-pointer text-xs font-medium">
          Supported fragment production types
        </summary>
        <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
          {[
            "pcr-amplified",
            "restriction-digest",
            "synthetic-dsdna",
            "ssdna-oligo",
            "annealed-oligos",
            "existing-linear",
            "amplified",
            "fixed",
            "literal",
          ].map((kind) => (
            <code key={kind} className="rounded bg-muted px-1.5 py-0.5">
              {kind}
            </code>
          ))}
        </div>
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
          A <code>restriction-digest</code> fragment requires typed restriction metadata in JSON
          mode. Sequences are expressed in final-construct orientation; source orientation is
          provenance.
        </p>
      </details>
    </div>
  );
}

/**
 * The variant, both its alleles, and how the primers are laid out.
 *
 * The position has nothing to default to — the whole design is anchored on one
 * base — and both alleles are required, because a genotype is read by comparing
 * two reactions and one on its own cannot tell a homozygote from a tube that
 * failed.
 */
export function VariantFields({
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
  const variantType = value("variantType") || "snv";

  if (section === "reaction") {
    if (moduleId === "kasp") {
      const protocol = value("kaspProtocol");
      const named = protocol === "lgc-kasp-tf-v5" || protocol === "lgc-standard";
      return (
        <div className="space-y-4 rounded-lg border border-border/60 bg-surface-wash/25 p-4">
          <div>
            <h3 className="font-serif text-base font-semibold">
              KASP endpoint reaction & evidence
            </h3>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              KASP design and endpoint calling are separate contracts. Primer geometry can be
              predicted; FAM/HEX clusters, controls, call rate and concordance are measured run
              data.
            </p>
          </div>
          <div>
            <Label htmlFor="kaspProtocol" className="text-xs">
              Wet-lab protocol overlay
            </Label>
            <select
              id="kaspProtocol"
              required
              value={protocol}
              onChange={(e) => onChange("kaspProtocol", e.target.value)}
              className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm sm:max-w-xl"
            >
              <option value="">Choose exact protocol</option>
              <option value="lgc-kasp-tf-v5">
                LGC KASP-TF V5.0 Master Mix · current reviewed branch
              </option>
            </select>
          </div>
          {named ? (
            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                <Label htmlFor="kaspPlateFormat" className="text-xs">
                  Plate format
                </Label>
                <select
                  id="kaspPlateFormat"
                  required
                  value={value("kaspPlateFormat")}
                  onChange={(e) => onChange("kaspPlateFormat", e.target.value)}
                  className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
                >
                  <option value="">Choose plate</option>
                  <option value="96">96 well</option>
                  <option value="384">384 well</option>
                </select>
              </div>
              <EvidenceInput
                id="kaspInstrumentModel"
                label="Instrument model"
                value={value}
                onChange={onChange}
                placeholder="model or unresolved"
              />
              <div>
                <Label htmlFor="kaspRoxPolicy" className="text-xs">
                  ROX / passive reference
                </Label>
                <select
                  id="kaspRoxPolicy"
                  required
                  value={value("kaspRoxPolicy")}
                  onChange={(e) => onChange("kaspRoxPolicy", e.target.value)}
                  className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
                >
                  <option value="">Record explicitly</option>
                  <option value="unresolved">Unresolved</option>
                  <option value="none">None</option>
                  <option value="low">Low</option>
                  <option value="standard">Standard</option>
                  <option value="high">High</option>
                </select>
              </div>
            </div>
          ) : null}

          <details className="rounded-lg border border-border/60 bg-background/35 p-3">
            <summary className="cursor-pointer text-xs font-medium">
              Endpoint validation evidence
            </summary>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <EvidenceInput
                id="kaspSamples"
                label="Samples"
                type="number"
                value={value}
                onChange={onChange}
              />
              <EvidenceInput
                id="kaspCalledSamples"
                label="Called samples"
                type="number"
                value={value}
                onChange={onChange}
              />
              <EvidenceInput
                id="kaspCallRatePercent"
                label="Call rate (%)"
                type="number"
                value={value}
                onChange={onChange}
              />
              <EvidenceInput
                id="kaspControlConcordancePercent"
                label="Control concordance (%)"
                type="number"
                value={value}
                onChange={onChange}
              />
              <EvidenceInput
                id="kaspNtcStatus"
                label="NTC status"
                value={value}
                onChange={onChange}
              />
              <EvidenceInput
                id="kaspKnownGenotypeControls"
                label="Known-genotype controls"
                value={value}
                onChange={onChange}
              />
              <EvidenceInput
                id="kaspRareAlleleControl"
                label="Rare-allele positive control"
                value={value}
                onChange={onChange}
              />
              <EvidenceInput
                id="kaspInstrumentSoftware"
                label="Instrument / software"
                value={value}
                onChange={onChange}
              />
              <EvidenceInput
                id="kaspEndpointDataReference"
                label="Endpoint data reference"
                value={value}
                onChange={onChange}
              />
              <EvidenceInput
                id="kaspClusterReview"
                label="Cluster review"
                value={value}
                onChange={onChange}
              />
              <EvidenceInput
                id="kaspAmbiguousWells"
                label="Ambiguous / no-call wells"
                value={value}
                onChange={onChange}
              />
              <EvidenceInput
                id="kaspValidationNotes"
                label="Validation notes"
                value={value}
                onChange={onChange}
              />
            </div>
            <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
              FAM is the X axis and HEX the Y axis. PCRStudio does not auto-label clusters from
              primer tails alone.
            </p>
          </details>
        </div>
      );
    }

    if (moduleId === "tetra-primer-arms") {
      return (
        <div className="space-y-4 rounded-lg border border-border/60 bg-surface-wash/25 p-4">
          <div>
            <h3 className="font-serif text-base font-semibold">
              Tetra-ARMS electrophoresis context
            </h3>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              Three predicted products are useful only if the intended readout can resolve them.
              PCRStudio therefore records the actual readout context instead of inventing a
              universal bp threshold or primer ratio.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <Label htmlFor="tetraReadout" className="text-xs">
                Readout
              </Label>
              <select
                id="tetraReadout"
                required
                value={value("tetraReadout")}
                onChange={(e) => onChange("tetraReadout", e.target.value)}
                className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
              >
                <option value="">Choose readout</option>
                <option value="agarose-gel">Agarose gel</option>
                <option value="page">PAGE</option>
                <option value="capillary">Capillary electrophoresis</option>
                <option value="unresolved">Unresolved / custom</option>
              </select>
            </div>
            <EvidenceInput
              id="tetraMinBandSeparationBp"
              label="Minimum resolvable gap (bp)"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="tetraGelPercent"
              label="Gel concentration (%)"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="tetraLadder"
              label="Ladder / size standard"
              value={value}
              onChange={onChange}
            />
          </div>
          <EvidenceInput
            id="tetraRunContext"
            label="Run context / SOP"
            value={value}
            onChange={onChange}
          />
          <details className="rounded-lg border border-border/60 bg-background/35 p-3">
            <summary className="cursor-pointer text-xs font-medium">
              Observed validation evidence
            </summary>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <EvidenceInput
                id="tetraReplicates"
                label="Replicates"
                type="number"
                value={value}
                onChange={onChange}
              />
              <EvidenceInput
                id="tetraConcordantCalls"
                label="Concordant calls"
                type="number"
                value={value}
                onChange={onChange}
              />
              <EvidenceInput
                id="tetraNtcStatus"
                label="NTC status"
                value={value}
                onChange={onChange}
              />
              <EvidenceInput
                id="tetraKnownGenotypeControls"
                label="Known-genotype controls"
                value={value}
                onChange={onChange}
              />
              <EvidenceInput
                id="tetraObservedBands"
                label="Observed diagnostic bands"
                value={value}
                onChange={onChange}
              />
              <EvidenceInput
                id="tetraOuterControlBand"
                label="Outer-control band"
                value={value}
                onChange={onChange}
              />
              <EvidenceInput
                id="tetraGelImageReference"
                label="Gel image / raw data reference"
                value={value}
                onChange={onChange}
              />
              <EvidenceInput
                id="tetraValidationNotes"
                label="Validation notes"
                value={value}
                onChange={onChange}
              />
            </div>
          </details>
        </div>
      );
    }

    return (
      <div className="space-y-4 rounded-lg border border-border/60 bg-surface-wash/25 p-4">
        <div>
          <h3 className="font-serif text-base font-semibold">
            ARMS-PCR mismatch chemistry & validation
          </h3>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            The current mismatch evidence is scoped to Taq-like non-proofreading chemistry and
            candidate ranking. It is never a polymerase-independent extension law.
          </p>
        </div>
        <details className="rounded-lg border border-border/60 bg-background/35 p-3">
          <summary className="cursor-pointer text-xs font-medium">
            Two-tube validation evidence
          </summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <EvidenceInput
              id="armsReplicates"
              label="Replicates"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="armsConcordantCalls"
              label="Concordant calls"
              type="number"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="armsNtcStatus"
              label="NTC status"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="armsPositiveControlA"
              label="Allele-A control"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="armsPositiveControlB"
              label="Allele-B control"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="armsHeterozygousControl"
              label="Heterozygous control"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="armsObservedReadout"
              label="Observed readout"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="armsRawDataReference"
              label="Raw-data reference"
              value={value}
              onChange={onChange}
            />
            <EvidenceInput
              id="armsValidationNotes"
              label="Validation notes"
              value={value}
              onChange={onChange}
            />
          </div>
        </details>
      </div>
    );
  }

  return (
    <div className="space-y-4 rounded-lg border border-border/60 bg-surface-wash/25 p-4">
      <div>
        <h3 className="font-serif text-base font-semibold">Normalized variant anchor</h3>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          Exact REF/ALT, coordinate system and reference provenance are retained. MNVs and indels
          are never silently collapsed to a single-base identity; an allele-specific anchor, when
          needed, is a transparent derived design decision.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <Label htmlFor="variantType" className="text-xs">
            Variant class
          </Label>
          <select
            id="variantType"
            required
            value={variantType}
            onChange={(e) => {
              const next = e.target.value;
              onChange("variantType", next);
              if (moduleId === "kasp") {
                onChange(
                  "kaspAssayMode",
                  next === "snv" || next === "mnv"
                    ? "biallelic-genotype"
                    : "plus-minus-presence-absence",
                );
              }
            }}
            className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
          >
            <option value="snv">SNV</option>
            <option value="mnv">MNV</option>
            {moduleId === "kasp" ? (
              <>
                <option value="insertion">Insertion</option>
                <option value="deletion">Deletion</option>
                <option value="complex-replacement">Complex replacement</option>
                <option value="presence-absence">Presence / absence</option>
              </>
            ) : null}
          </select>
        </div>
        <EvidenceInput
          id="variantAt"
          label="Reference position / boundary"
          type="number"
          value={value}
          onChange={onChange}
          placeholder="1-based in UI"
        />
        <EvidenceInput
          id="variantRef"
          label={
            variantType === "insertion"
              ? "REF (leave empty)"
              : variantType === "presence-absence"
                ? "REF (present sequence)"
                : "REF"
          }
          value={value}
          onChange={onChange}
        />
        <EvidenceInput
          id="variantAlt"
          label={
            variantType === "deletion" || variantType === "presence-absence"
              ? "ALT (leave empty)"
              : "ALT"
          }
          value={value}
          onChange={onChange}
        />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <EvidenceInput
          id="variantReferenceAccession"
          label="Reference accession.version"
          value={value}
          onChange={onChange}
        />
        <EvidenceInput
          id="variantAssembly"
          label="Assembly / build"
          value={value}
          onChange={onChange}
        />
        <div>
          <Label htmlFor="variantCoordinateSystem" className="text-xs">
            Coordinate system
          </Label>
          <select
            id="variantCoordinateSystem"
            value={value("variantCoordinateSystem") || "0-based-reference"}
            onChange={(e) => onChange("variantCoordinateSystem", e.target.value)}
            className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
          >
            <option value="0-based-reference">0-based reference internally</option>
            <option value="0-based-half-open">0-based half-open</option>
          </select>
        </div>
        <div>
          <Label htmlFor="variantStrand" className="text-xs">
            Variant strand
          </Label>
          <select
            id="variantStrand"
            value={value("variantStrand") || "plus"}
            onChange={(e) => onChange("variantStrand", e.target.value)}
            className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
          >
            <option value="plus">Plus</option>
            <option value="minus">Minus</option>
          </select>
        </div>
        <EvidenceInput
          id="variantRsid"
          label="rsID / external ID"
          value={value}
          onChange={onChange}
        />
      </div>

      {moduleId === "kasp" ? (
        <div className="sm:max-w-md">
          <Label htmlFor="kaspAssayMode" className="text-xs">
            KASP interpretation
          </Label>
          <select
            id="kaspAssayMode"
            required
            value={value("kaspAssayMode") || "biallelic-genotype"}
            onChange={(e) => onChange("kaspAssayMode", e.target.value)}
            className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
          >
            <option
              value="biallelic-genotype"
              disabled={variantType !== "snv" && variantType !== "mnv"}
            >
              Biallelic genotype · SNV/MNV
            </option>
            <option
              value="plus-minus-presence-absence"
              disabled={variantType === "snv" || variantType === "mnv"}
            >
              Plus/minus presence–absence · indel/complex
            </option>
          </select>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            Plus/minus is a junction-aware presence/absence topology. Presence–absence uses REF as
            the present sequence on the submitted reference and an empty ALT; use insertion when the
            reference is the absence allele. It is never reinterpreted as an ordinary diploid SNV.
          </p>
        </div>
      ) : null}

      <div className="grid gap-3 lg:grid-cols-2">
        <div>
          <Label htmlFor="nearbyVariantsVcf" className="text-xs">
            Nearby-variant VCF mask (optional)
          </Label>
          <textarea
            id="nearbyVariantsVcf"
            value={value("nearbyVariantsVcf")}
            onChange={(e) => onChange("nearbyVariantsVcf", e.target.value)}
            rows={6}
            spellCheck={false}
            placeholder={"#CHROM\tPOS\tID\tREF\tALT\nNC_...\t12345\trs...\tA\tG"}
            className="mt-1 w-full rounded-lg border-border/70 bg-surface-wash/35 p-2 font-mono text-xs"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Caller-supplied finite VCF only; PCRStudio does not infer population frequency or
            silently fetch a different assembly.
          </p>
        </div>
        <div>
          <Label htmlFor="mismatchEvidenceProfile" className="text-xs">
            Mismatch evidence profile
          </Label>
          <select
            id="mismatchEvidenceProfile"
            value={
              value("mismatchEvidenceProfile") ||
              "pcrstudio-gen1-taq-terminal-mismatch-evidence-2026"
            }
            onChange={(e) => onChange("mismatchEvidenceProfile", e.target.value)}
            className="mt-1 h-9 w-full rounded-lg border-border/70 bg-surface-wash/35 px-2 text-sm"
          >
            <option value="pcrstudio-gen1-taq-terminal-mismatch-evidence-2026">
              PCRStudio 2026 · Taq-scoped terminal mismatch evidence
            </option>
          </select>
          <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
            This profile may rank candidates; empirical paired-allele validation is still required
            and no mismatch class is a guaranteed block.
          </p>
        </div>
      </div>
    </div>
  );
}

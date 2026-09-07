"use client";

/**
 * What a genotyping design produced.
 *
 * The number this view has to put in front of somebody is not a melting
 * temperature. It is what the assay actually discriminates on, because that
 * varies with the variant in a way nothing about the primers reveals.
 *
 * Both alleles are given, so the terminal mismatch is dealt rather than chosen;
 * the only lever is which strand each allele-specific primer sits on. For a
 * transversion the evidence table used by Gen-1 can assign the strongest
 * terminal-mismatch class to different alleles on opposite strands. That is a
 * candidate-selection signal, not a universal extension/no-extension law. For
 * a transition, this evidence table does not provide that strong class, so the
 * candidate policy explores a second, deliberate near-terminal mismatch whose
 * usefulness still has to be established experimentally.
 *
 * A result that showed two primers and two temperatures would look identical in
 * all three cases. So each allele carries a plain statement of what separates it
 * from the other, and the deliberate mismatch is marked in the sequence — it
 * disagrees with the template on purpose and otherwise reads as a typing error.
 */

import { ResultFact as Fact, RuntimeProvenance } from "./result-primitives";
import { ScanFindings } from "@/components/design/scan";
import { OrderActions } from "./order-actions";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { count } from "@/lib/numbers";
import type { DiscriminatingResult } from "@/lib/api/types";
import { KaspEndpointWorkspace } from "./kasp-endpoint-workspace";
import { WorkflowEvidenceCard } from "./workflow-evidence";

/** How each class of terminal mismatch reads to somebody at a bench. */
const STRENGTH: Record<string, { label: string; className: string }> = {
  blocks: {
    label: "is in the strongest reduction class of the cited model",
    className: "border-success/40 bg-success/5",
  },
  slows: {
    label: "is in a moderate-reduction class of the cited model",
    className: "border-warning/40 bg-warning/5",
  },
  depends: {
    label: "is sequence-context dependent in the cited model",
    className: "border-warning/40 bg-warning/5",
  },
  tolerated: {
    label: "is in the lowest-discrimination class of the cited model",
    className: "border-destructive/40 bg-destructive/5",
  },
};

export function DiscriminatingResultView({ result }: { result: DiscriminatingResult }) {
  return (
    <div className="space-y-5">
      <TheVariant result={result} />
      {result.protocol ? <KaspProtocol result={result} /> : null}
      {result.kasp ? <KaspEndpointWorkspace /> : null}
      <WorkflowEvidenceCard
        evidence={result.workflow_evidence}
        title="Genotyping validation evidence"
      />

      {result.primers.length > 0 ? (
        <>
          <Alleles result={result} />
          {result.partners.length > 0 ? <Partners result={result} /> : null}
          {result.band_geometry ? <BandGeometry result={result} /> : null}
          <OrderSheet result={result} />
        </>
      ) : null}

      {Object.keys(result.refused).length > 0 || result.why_nothing ? (
        <Refused result={result} />
      ) : null}

      <RuntimeProvenance provenance={result.provenance} />
    </div>
  );
}

/** The selected LGC overlay, kept separate from the primer-search numbers. */
function KaspProtocol({ result }: { result: DiscriminatingResult }) {
  const protocol = result.protocol;
  if (!protocol) return null;
  const currentV5 = protocol.source_revision === "V5.0";
  const readout = protocol.readout as { channels?: string[]; [key: string]: unknown } | undefined;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">
          Selected wet-lab protocol authority
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs font-medium">{protocol.selection}</p>
        <dl className="grid gap-x-6 gap-y-2 text-xs sm:grid-cols-4">
          <Fact
            label="Plate"
            value={protocol.plate_format ? `${protocol.plate_format}-well` : "not recorded"}
          />
          <Fact label="Instrument" value={protocol.instrument_model ?? "not recorded"} />
          <Fact label="ROX / reference" value={protocol.rox_policy ?? "not recorded"} />
          <Fact label="Readout" value={readout?.channels?.join(" / ") ?? "FAM / HEX"} />
        </dl>
        {currentV5 ? (
          <div className="rounded-md border border-warning/35 bg-warning/5 p-2.5 text-xs leading-relaxed text-muted-foreground">
            V5 is source-limited in this authority snapshot. PCRStudio retains the current
            endpoint/readout and additional-cycle semantics, but it does not copy historical V4
            dispensing or primary-cycling numbers into V5 where the reviewed V5 source does not
            establish them.
          </div>
        ) : null}
        {protocol.source_identity ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            Source: {protocol.source_identity}
            {protocol.source_revision
              ? ` · ${protocol.source_revision}`
              : " · revision not recorded"}
            .
          </p>
        ) : null}
        {protocol.note ? (
          <p className="text-xs leading-relaxed text-muted-foreground">{protocol.note}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}

/** What kind of variant this is, which decides what the assay can promise. */
function TheVariant({ result }: { result: DiscriminatingResult }) {
  const { variant, geometry } = result;
  const alleleLabel = variant.alleles?.length
    ? variant.alleles.join(" / ")
    : [variant.ref, variant.alt]
        .filter((value): value is string => value != null)
        .map((value) => value || "∅")
        .join(" / ") || variant.kind;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">
          {alleleLabel} at base {count(variant.at)}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <dl className="grid gap-x-6 gap-y-2 text-xs sm:grid-cols-3 lg:grid-cols-4">
          <Fact label="Variant class" value={variant.kind} />
          <Fact label="Layout" value={geometry.name} />
          <Fact
            label="Reactions"
            value={geometry.tubes === 1 ? "one tube" : `${geometry.tubes} tubes`}
          />
          <Fact label="Reference" value={variant.reference_accession ?? "not recorded"} />
          <Fact label="Assembly/build" value={variant.assembly ?? "not recorded"} />
          <Fact label="Coordinate system" value={variant.coordinate_system ?? "not recorded"} />
          <Fact label="Strand" value={variant.strand ?? "not recorded"} />
          <Fact label="rsID" value={variant.rsid ?? "not recorded"} />
        </dl>
        {result.kasp ? (
          <div className="rounded-md border border-primary/25 bg-primary/5 p-2.5">
            <dl className="grid gap-x-6 gap-y-2 text-xs sm:grid-cols-4">
              <Fact label="Chemistry" value={result.kasp.chemistry_family} />
              <Fact label="Assay mode" value={result.kasp.assay_mode} />
              <Fact label="Format" value={result.kasp.singleplex ? "singleplex" : "not declared"} />
              <Fact label="Claim state" value={result.kasp.call_status} />
            </dl>
            {result.kasp.call_model ? (
              <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                Call model is topology metadata only; measured endpoint clusters remain a separate
                evidence layer.
              </p>
            ) : null}
            <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
              The software predicts an experimental KASP-compatible assay proposal; it does not turn
              endpoint fluorescence into a validated genotype call without plate/control evidence.
              {result.kasp.design_authority ? ` ${result.kasp.design_authority.note}` : ""}
            </p>
          </div>
        ) : null}
        {result.variant_masking ? (
          <div className="rounded-md border border-border/60 bg-surface-wash/20 p-2.5 text-xs leading-relaxed text-muted-foreground">
            Nearby-variant masking is bounded to the supplied evidence source. PCRStudio does not
            infer population frequency or absence of other polymorphisms from a finite VCF.
          </div>
        ) : null}
        {variant.note ? (
          <p className="text-xs leading-relaxed text-muted-foreground">{variant.note}</p>
        ) : null}
        <p className="text-xs leading-relaxed text-muted-foreground">{geometry.note}</p>
      </CardContent>
    </Card>
  );
}

/** Each allele's primer, led by what actually separates it from the other. */
function Alleles({ result }: { result: DiscriminatingResult }) {
  return (
    <div className="space-y-3">
      {result.primers.map((primer) => {
        const how = result.discrimination[primer.allele];
        const strength = how ? STRENGTH[how.terminus_strength] : undefined;

        return (
          <Card key={primer.name}>
            <CardHeader className="flex flex-row items-baseline justify-between gap-3 space-y-0">
              <CardTitle className="text-[13px] font-medium">
                Specific for {primer.allele}
              </CardTitle>
              <span className="text-xs text-muted-foreground">
                {primer.strand} strand · {primer.tm} °C
              </span>
            </CardHeader>

            <CardContent className="space-y-3">
              {/* The sequence with the two deliberate positions marked: the
                  variant at the 3' end, and the second mismatch if there is
                  one. Reading it without those marked, the second mismatch is
                  indistinguishable from an error. */}
              <p className="font-mono text-xs break-all">
                {/* The cassette tail set apart, because it is not on the
                    template: it is copied into the product in round one and
                    read from round two on. Shown as part of one molecule
                    rather than as a separate line, since it is ordered as one.
                    The marks below count from the 3' end, so they land on the
                    same bases whether or not a tail is in front. */}
                {primer.cassette ? (
                  <span className="text-muted-foreground">{primer.cassette.tail}</span>
                ) : null}
                {marked(
                  primer.cassette ? primer.cassette.annealing : primer.sequence,
                  how?.second_mismatch?.at ?? null,
                )}
              </p>

              {primer.cassette ? (
                <p className="text-xs leading-relaxed text-muted-foreground">
                  <span className="font-medium text-foreground">{primer.cassette.dye}</span> ·{" "}
                  {primer.cassette.note}
                </p>
              ) : null}

              {how ? (
                <div
                  className={`space-y-1.5 rounded-md border p-2.5 ${
                    how.rests_on === "nothing"
                      ? "border-destructive/40 bg-destructive/5"
                      : "border-primary/30 bg-primary/5"
                  }`}
                >
                  <p className="text-xs font-medium">
                    {how.rests_on === "terminus"
                      ? "Design relies on the variant-base mismatch"
                      : how.rests_on === "second mismatch"
                        ? "Design relies on a proposed second mismatch"
                        : "No supported discrimination proposal"}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Its 3&prime; end makes a <span className="font-mono">{how.terminus}</span> pair
                    against the other allele, which {strength?.label ?? how.terminus_strength}.
                  </p>
                  {how.second_mismatch ? (
                    <p className="text-xs text-muted-foreground">
                      Carries {how.second_mismatch.was} → {how.second_mismatch.now} at position{" "}
                      {how.second_mismatch.at}. {how.second_mismatch.why}
                    </p>
                  ) : null}
                </div>
              ) : null}

              <p className="text-xs leading-relaxed text-muted-foreground">{primer.note}</p>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

/**
 * The sequence with the deliberate positions marked.
 *
 * The last base is the variant; the other, when there is one, is the
 * substitution that does the discriminating on a transition.
 */
function marked(sequence: string, secondAt: number | null) {
  const second = secondAt === null ? -1 : sequence.length + secondAt;
  return [...sequence].map((base, index) => {
    if (index === sequence.length - 1) {
      return (
        <span key={index} className="rounded-sm bg-primary/35 px-0.5">
          {base}
        </span>
      );
    }
    if (index === second) {
      return (
        <span key={index} className="rounded-sm bg-warning/40 px-0.5">
          {base}
        </span>
      );
    }
    return <span key={index}>{base}</span>;
  });
}

function BandGeometry({ result }: { result: DiscriminatingResult }) {
  const geometry = result.band_geometry;
  if (!geometry) return null;
  const alleles = Object.entries(geometry.allele_products_bp);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">
          Tetra-ARMS diagnostic band geometry
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-xs">
        <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-4">
          {alleles.map(([allele, size]) => (
            <Fact key={allele} label={`${allele} allele product`} value={`${count(size)} bp`} />
          ))}
          <Fact label="Outer control product" value={`${count(geometry.outer_control_bp)} bp`} />
          <Fact
            label="Smallest size gap"
            value={`${count(geometry.minimum_pairwise_separation_bp)} bp`}
          />
        </dl>
        <p className="text-xs leading-relaxed text-muted-foreground">
          Computational topology:{" "}
          {geometry.topology_complete ? "complete three-product geometry" : "incomplete"}.
          Resolution check: {geometry.resolution_status}
          {geometry.required_minimum_separation_bp == null
            ? ""
            : ` against the declared workflow minimum of ${geometry.required_minimum_separation_bp} bp`}
          . This is a size-separation check, not proof that all three products amplify with
          comparable efficiency on a particular gel or capillary system.
        </p>
      </CardContent>
    </Card>
  );
}

function Partners({ result }: { result: DiscriminatingResult }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">
          {result.partners.length === 1 ? "The common primer" : "The common primers"}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {result.partners.map((partner) => (
          <div key={partner.sequence} className="rounded-md border p-2.5">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <span className="text-xs font-medium">for {partner.for_alleles.join(" and ")}</span>
              <span className="text-xs text-muted-foreground tabular-nums">
                {partner.product_size} bp · {partner.tm} °C · {partner.tm_difference} °C apart
              </span>
            </div>
            <p className="mt-1 font-mono text-xs break-all">{partner.sequence}</p>
            <p className="mt-1 text-xs text-muted-foreground">{partner.note}</p>
          </div>
        ))}

        {/*
         * Counted across every oligo in the assay at once, because it runs as
         * one experiment: an allele-specific primer that pairs with the other
         * tube's partner is exactly the band that reads as a heterozygote.
         */}
        <ScanFindings off={result.off_targets} intended={0} />
      </CardContent>
    </Card>
  );
}

function Refused({ result }: { result: DiscriminatingResult }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[13px] font-medium">What could not be made</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {Object.entries(result.refused).map(([allele, why]) => (
          <p
            key={allele}
            className="rounded-md border border-destructive/40 bg-destructive/5 p-2.5 text-xs leading-relaxed"
          >
            {why}
          </p>
        ))}
        {result.why_nothing && !Object.keys(result.refused).length ? (
          <p className="text-xs leading-relaxed text-muted-foreground">{result.why_nothing}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function OrderSheet({ result }: { result: DiscriminatingResult }) {
  const orderability = result.orderability ?? {
    orderable: false,
    status: "historical-result-orderability-not-recorded",
    note: "This saved discriminating-assay result predates the current completeness/orderability contract. Regenerate with the current worker before ordering any oligos.",
  };
  if (!orderability.orderable) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-[13px] font-medium">Diagnostic assay — do not order</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <p className="text-xs font-medium">{orderability.status}</p>
          <p className="text-xs leading-relaxed text-muted-foreground">{orderability.note}</p>
        </CardContent>
      </Card>
    );
  }
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle className="text-[13px] font-medium">
          What to order — {result.order_sheet.length} oligos
        </CardTitle>
        <OrderActions
          lines={result.order_sheet}
          kind="allele-primers"
          conditions={result.reaction}
        />
      </CardHeader>
      <CardContent className="space-y-2">
        {result.order_sheet.map((line) => (
          <div key={line.name} className="rounded-md border p-2.5">
            <div className="flex items-baseline justify-between gap-3">
              <span className="font-mono text-xs font-medium">{line.name}</span>
              <span className="text-xs text-muted-foreground tabular-nums">
                {line.length} nt · {line.tm} °C
              </span>
            </div>
            <p className="mt-1 font-mono text-xs break-all">{line.sequence}</p>
            {/* The line that stops somebody "correcting" a primer back to the
                template before they order it. */}
            {line.note?.includes("deliberate") ? (
              <p className="mt-1 text-xs font-medium text-primary">{line.note}</p>
            ) : line.note ? (
              <p className="mt-1 text-xs text-muted-foreground">{line.note}</p>
            ) : null}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

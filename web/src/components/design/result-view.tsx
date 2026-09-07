"use client";

import { DesignResultView } from "@/components/design/design-result";
import { DiscriminatingResultView } from "@/components/design/discriminating-result";
import { JunctionResultView } from "@/components/design/junction-result";
import { LoopSetResultView } from "@/components/design/loop-set-result";
import { MutagenicResultView } from "@/components/design/mutagenic-result";
import { NestedResultView } from "@/components/design/nested-result";
import { OutwardResultView } from "@/components/design/outward-result";
import { ProbeResultView } from "@/components/design/probe-result";
import { SingleResultView } from "@/components/design/single-result";
import { TilingResultView } from "@/components/design/tiling-result";
import { ToolchainStatus } from "@/components/design/toolchain-status";
import { ResultOverview } from "@/components/design/result-overview";
import { UniversalResultView } from "@/components/design/universal-result";
import { FivePrimeTails } from "@/components/design/five-prime-tails";
import { ScanSummary } from "@/components/design/scan";
import type { InclusivityAudit, ReverseTranscription, RunResult } from "@/lib/api/types";

/**
 * Which view renders a result.
 *
 * Decided by which engine answered, not by what the shape looks like — a guess
 * would render the wrong thing the day a twelfth engine arrives with a
 * familiar-looking field.
 *
 * It is its own component because two places need it: the workspace, and the
 * read-only view of a project whose design system is no longer in this build.
 * A chain this long living in one of them means the other renders ten engines
 * correctly and the eleventh as a generic pair, silently.
 *
 * Note what this does *not* need: the module. Every run records the engine that
 * produced it, so a saved result stays readable whether or not the system that
 * made it is still installed.
 */
export function ResultView({ result }: { result: RunResult }) {
  /*
   * Rendered here rather than in each of the five views that can carry it.
   *
   * The step is a property of the run — the same hold, at the same
   * temperature, whichever design you pick — so it belongs above the engine's
   * own answer rather than repeated on twenty cards. Five renderers would be
   * five chances to quote a different temperature.
   */
  const rt = "reverse_transcription" in result ? result.reverse_transcription : null;

  /*
   * Six of the eleven engines scan, and the five that do not have nothing to
   * say here — a Gibson junction has no template to be specific against. So
   * the summary is rendered where a result carries one and nowhere else,
   * rather than every view growing its own sentence about it.
   */
  const background = "background" in result ? result.background : undefined;

  return (
    <div className="space-y-5">
      <ResultOverview result={result} />

      <section id="result-context" className="scroll-mt-24 space-y-5" aria-label="Run context">
        {rt ? <ReverseTranscriptionStep step={rt} /> : null}
        {"background" in result ? <ScanSummary background={background} /> : null}
        {"inclusivity" in result && result.inclusivity ? (
          <InclusivitySummary audit={result.inclusivity} />
        ) : null}
        {/* Two engines' oligos go on to something else, and both say so here
            rather than each view growing its own sentence about it. */}
        {"tails" in result ? <FivePrimeTails tails={result.tails} /> : null}
      </section>

      <section id="result-verification" className="scroll-mt-24" aria-label="Verification evidence">
        <ToolchainStatus result={result} />
      </section>

      <section id="result-design" className="scroll-mt-24" aria-label="Design details">
        <EngineView result={result} />
      </section>
    </div>
  );
}

function InclusivitySummary({ audit }: { audit: InclusivityAudit }) {
  return (
    <section className="rounded-xl border border-border/70 bg-surface-wash/40 px-4 py-3 text-xs leading-relaxed">
      <h3 className="font-serif text-sm font-semibold">Target inclusivity screen</h3>
      <p className="mt-1 text-muted-foreground">
        {audit.template_only
          ? `One representative template record was checked across ${audit.pairs_checked} candidate pair(s).`
          : `${audit.contigs} target record(s) covering ${audit.bases.toLocaleString()} bases were checked across ${audit.pairs_checked} candidate pair(s).`}
      </p>
      {audit.pairs_rejected ? (
        <p className="mt-1 text-destructive">
          {audit.pairs_rejected} pair(s) failed to form a complete product across the target panel.
        </p>
      ) : null}
      {audit.ambiguous_bases ? (
        <p className="mt-1 text-muted-foreground">
          The panel contains {audit.ambiguous_bases.toLocaleString()} IUPAC-ambiguous base(s).
          Ambiguity at a primer-binding site is treated fail-closed rather than as exact target
          coverage.
        </p>
      ) : null}
      {audit.panel_sha256 ? (
        <p className="mt-1 font-mono text-xs break-all text-muted-foreground">
          Panel SHA-256: {audit.panel_sha256}
        </p>
      ) : null}
      {audit.panel_identity_claim ? (
        <p className="mt-1 text-muted-foreground">
          The fingerprint identifies the supplied normalized FASTA content; it does not certify
          taxonomic completeness or biological representativeness.
        </p>
      ) : null}
      {audit.panel_provenance ? (
        <p className="mt-1 text-muted-foreground">
          Panel provenance: <span className="text-foreground">{audit.panel_provenance}</span>
        </p>
      ) : null}
      {audit.panel_selection_rationale ? (
        <p className="mt-1 text-muted-foreground">
          Selection rationale:{" "}
          <span className="text-foreground">{audit.panel_selection_rationale}</span>
        </p>
      ) : null}
      {audit.taxonomy_resolution_status ? (
        <p className="mt-1 text-muted-foreground">
          Taxonomy: FASTA labels are not taxonomically resolved or validated by this run.
          User-declared provenance is retained for review but is not independently verified by
          PCRStudio; population-frequency coverage is not computed and continuing sequence
          surveillance remains external.
        </p>
      ) : null}
      {audit.topology_note ? (
        <p className="mt-1 text-muted-foreground">Topology: {audit.topology_note}</p>
      ) : null}
      <p className="mt-1 text-muted-foreground">{audit.note}</p>
    </section>
  );
}

/**
 * Reverse-transcription handoff for an RNA-starting run.
 *
 * Most named RT-PCR/RT-dPCR chemistries place RT before PCR cycling, while a
 * true one-pot isothermal chemistry can perform RT concurrently with
 * amplification.  Keep that timing semantic in the result instead of forcing
 * every RNA workflow into a misleading "before the programme" label.
 */
function ReverseTranscriptionStep({ step }: { step: NonNullable<ReverseTranscription> }) {
  const concurrent = step.before === "concurrent-with-rpa";
  const title = concurrent
    ? "One-pot reverse transcription concurrent with RPA"
    : step.before
      ? "Reverse transcription before amplification"
      : "Reverse-transcription handoff";
  return (
    <section className="rounded-xl border border-dashed border-border/60 bg-surface-wash/30 p-4">
      <h3 className="font-serif text-base font-semibold">{title}</h3>
      {step.hold ? (
        <p className="mt-2 text-sm tabular-nums">
          {step.hold.celsius} °C for{" "}
          {step.hold.seconds < 60
            ? `${step.hold.seconds} s`
            : `${Math.round(step.hold.seconds / 60)} min`}
        </p>
      ) : null}
      <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{step.note}</p>
    </section>
  );
}

function EngineView({ result }: { result: RunResult }) {
  switch (result.engine) {
    case "consensus-pair":
      return <UniversalResultView result={result} />;
    case "nested":
      return <NestedResultView result={result} />;
    case "outward-pair":
      return <OutwardResultView result={result} />;
    case "pair-and-probe":
      return <ProbeResultView result={result} />;
    case "single-primer":
      return <SingleResultView result={result} />;
    case "mutagenic-pair":
      return <MutagenicResultView result={result} />;
    case "tiling-scheme":
      return <TilingResultView result={result} />;
    case "junction-primers":
      return <JunctionResultView result={result} />;
    case "discriminating-pair":
      return <DiscriminatingResultView result={result} />;
    case "loop-set":
      return <LoopSetResultView result={result} />;
    default:
      return <DesignResultView result={result} />;
  }
}

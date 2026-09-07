"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { EngineFieldSection } from "./engine-field-types";

export function EngineClosureFields({
  engine,
  moduleId,
  section,
  value,
  onChange,
}: {
  engine: string;
  moduleId?: string;
  section: EngineFieldSection;
  value: (key: string) => string;
  onChange: (key: string, next: string) => void;
}) {
  if (engine === "outward-pair" && section === "strategy")
    return <OutwardClosure value={value} onChange={onChange} />;
  if (engine === "single-primer" && section === "design")
    return <SingleDesignClosure moduleId={moduleId} value={value} onChange={onChange} />;
  if (engine === "single-primer" && section === "reaction")
    return <SingleReactionClosure moduleId={moduleId} value={value} onChange={onChange} />;
  if (engine === "tiling-scheme" && section === "design")
    return <TilingDesignClosure value={value} onChange={onChange} />;
  if (engine === "tiling-scheme" && section === "reaction")
    return <TilingReactionClosure value={value} onChange={onChange} />;
  return null;
}

function OutwardClosure({ value, onChange }: Props) {
  return (
    <div className="space-y-3 rounded-lg border border-border/60 bg-surface-wash/25 p-4">
      <div>
        <h3 className="font-serif text-base font-semibold">Full-reference topology validation</h3>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          Optional complete-reference context turns inverse-PCR topology from an unresolved flank
          model into an exact restriction-fragment/circle reconstruction. It does not create an
          enzyme score.
        </p>
      </div>
      <div>
        <Label htmlFor="inverseReferenceSequence" className="text-xs">
          Complete reference molecule
        </Label>
        <textarea
          id="inverseReferenceSequence"
          value={value("inverseReferenceSequence")}
          onChange={(e) => onChange("inverseReferenceSequence", e.target.value)}
          rows={6}
          spellCheck={false}
          placeholder="Paste the complete linear/circular reference when available"
          className="mt-1 w-full rounded-lg border border-border/70 bg-background px-3 py-2 font-mono text-xs leading-relaxed focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={value("inverseReferenceCircular") === "true"}
            onChange={(e) =>
              onChange("inverseReferenceCircular", e.target.checked ? "true" : "false")
            }
          />{" "}
          Reference molecule is circular
        </label>
        <div>
          <Label htmlFor="inverseCandidateEnzymes" className="text-xs">
            Explicit enzyme cohort
          </Label>
          <Input
            id="inverseCandidateEnzymes"
            value={value("inverseCandidateEnzymes")}
            onChange={(e) => onChange("inverseCandidateEnzymes", e.target.value)}
            placeholder="EcoRI, HindIII, BamHI"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Caller order is preserved; feasibility is reported without a synthetic cross-enzyme
            score.
          </p>
        </div>
      </div>
    </div>
  );
}

function SingleDesignClosure({ moduleId, value, onChange }: Props & { moduleId?: string }) {
  if (moduleId === "race")
    return (
      <div className="rounded-lg border border-border/60 bg-surface-wash/25 p-4">
        <label className="flex items-start gap-2 text-xs">
          <input
            type="checkbox"
            className="mt-0.5"
            checked={value("racePolyadenylated") === "true"}
            onChange={(e) => onChange("racePolyadenylated", e.target.checked ? "true" : "false")}
          />
          <span>
            <strong>Transcript is polyadenylated.</strong>
            <span className="mt-1 block text-muted-foreground">
              Required for the SMARTer 3′ RACE poly(A)-anchored branch; no poly(A) state is inferred
              from the target sequence.
            </span>
          </span>
        </label>
      </div>
    );
  if (moduleId !== "sequencing-primer") return null;
  return (
    <div className="space-y-3 rounded-lg border border-border/60 bg-surface-wash/25 p-4">
      <div>
        <h3 className="font-serif text-base font-semibold">Primer walking</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Plans overlapping independent sequencing windows. Actual coverage remains trace evidence,
          not a design-time promise.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={value("sequencingPrimerWalking") === "true"}
            onChange={(e) =>
              onChange("sequencingPrimerWalking", e.target.checked ? "true" : "false")
            }
          />{" "}
          Plan primer walking
        </label>
        {value("sequencingPrimerWalking") === "true" ? (
          <div>
            <Label htmlFor="sequencingWalkingOverlap" className="text-xs">
              Planned overlap (bp)
            </Label>
            <Input
              id="sequencingWalkingOverlap"
              type="number"
              min={0}
              value={value("sequencingWalkingOverlap") || "100"}
              onChange={(e) => onChange("sequencingWalkingOverlap", e.target.value)}
            />
          </div>
        ) : null}
      </div>
    </div>
  );
}

function SingleReactionClosure({ moduleId, value, onChange }: Props & { moduleId?: string }) {
  if (moduleId !== "sequencing-primer") return null;
  return (
    <details className="rounded-lg border border-border/60 bg-surface-wash/25 p-4">
      <summary className="cursor-pointer text-xs font-medium">AB1 trace review</summary>
      <div className="mt-3 space-y-3">
        <div>
          <Label htmlFor="sequencingTraceFilename" className="text-xs">
            Trace filename
          </Label>
          <Input
            id="sequencingTraceFilename"
            value={value("sequencingTraceFilename")}
            onChange={(e) => onChange("sequencingTraceFilename", e.target.value)}
            placeholder="sample.ab1"
          />
        </div>
        <div>
          <Label htmlFor="sequencingTraceAb1Base64" className="text-xs">
            AB1 file as base64
          </Label>
          <textarea
            id="sequencingTraceAb1Base64"
            value={value("sequencingTraceAb1Base64")}
            onChange={(e) => onChange("sequencingTraceAb1Base64", e.target.value)}
            rows={5}
            spellCheck={false}
            placeholder="Paste base64-encoded ABIF/AB1 content (max decoded size 4 MiB)"
            className="mt-1 w-full rounded-lg border border-border/70 bg-background px-3 py-2 font-mono text-xs leading-relaxed focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            PBAS/PLOC/PCON/DATA evidence is bounded and post-run only; it never re-ranks the
            original primer.
          </p>
        </div>
      </div>
    </details>
  );
}

function TilingDesignClosure({ value, onChange }: Props) {
  const enabled =
    (value("tilingBackend") || "primalscheme3") === "primalscheme3" &&
    (value("tilingOperation") || "scheme-create") === "scheme-create";
  return (
    <div className="rounded-lg border border-border/60 bg-surface-wash/25 p-4">
      <label className="flex items-start gap-2 text-xs">
        <input
          type="checkbox"
          disabled={!enabled}
          checked={value("circular") === "true"}
          onChange={(e) => onChange("circular", e.target.checked ? "true" : "false")}
        />
        <span>
          <strong>Circular reference / origin-spanning scheme</strong>
          <span className="mt-1 block text-muted-foreground">
            Supported for PrimalScheme3 scheme-create. Repair/panel/replace stay fail-closed where
            the upstream lifecycle does not expose the same circular switch.
          </span>
        </span>
      </label>
    </div>
  );
}

function TilingReactionClosure({ value, onChange }: Props) {
  return (
    <details className="rounded-lg border border-border/60 bg-surface-wash/25 p-4">
      <summary className="cursor-pointer text-xs font-medium">
        Import measured amplicon depth
      </summary>
      <div className="mt-3 space-y-3">
        <div className="sm:max-w-xs">
          <Label htmlFor="tilingDropoutThreshold" className="text-xs">
            Dropout review threshold (depth)
          </Label>
          <Input
            id="tilingDropoutThreshold"
            type="number"
            min={0}
            step="any"
            value={value("tilingDropoutThreshold") || "20"}
            onChange={(e) => onChange("tilingDropoutThreshold", e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor="tilingDepthTsv" className="text-xs">
            Amplicon depth TSV
          </Label>
          <textarea
            id="tilingDepthTsv"
            value={value("tilingDepthTsv")}
            onChange={(e) => onChange("tilingDepthTsv", e.target.value)}
            rows={7}
            spellCheck={false}
            placeholder={"amplicon\tdepth\namplicon_1\t531\namplicon_2\t12"}
            className="mt-1 w-full rounded-lg border border-border/70 bg-background px-3 py-2 font-mono text-xs leading-relaxed focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Observed dropout nominates a repair review only; no causal primer/variant claim is
            inferred and the saved design ranking is not rewritten.
          </p>
        </div>
      </div>
    </details>
  );
}

type Props = { value: (key: string) => string; onChange: (key: string, next: string) => void };

"use client";

import { useState } from "react";

import { EnzymePanel, VectorPrimerPanel } from "@/components/design/bench-tools";
import { CheckPrimers } from "@/components/design/check-primers";
import { CloningTails } from "@/components/design/cloning-tails";
import type { ToolId } from "@/components/design/page-plan";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { RawDraftValues } from "@/lib/projects/draft";
import { placeVectorPrimersAction, rankEnzymesAction } from "@/lib/projects/actions";

type Draft = RawDraftValues;

export function Step({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <Card className="workbench-card">
      <CardHeader className="border-b bg-primary/5 pb-3">
        <CardTitle
          id="workspace-step-heading"
          tabIndex={-1}
          className="font-serif text-base font-semibold text-foreground focus-visible:outline-none"
        >
          {title}
        </CardTitle>
        <p className="text-xs leading-relaxed text-muted-foreground">{description}</p>
      </CardHeader>
      <CardContent className="space-y-4 pt-4">{children}</CardContent>
    </Card>
  );
}

export function Small({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 space-y-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm break-words">{value}</dd>
    </div>
  );
}

/**
 * The questions about what is already on the bench — for the assays that ask
 * them.
 *
 * Placed with the sequence rather than with the results because both change
 * what a design should be: which enzyme leaves the complete known inverse-PCR
 * anchor intact decides whether the standard flank-recovery branch is viable,
 * and which universal primers sit in the vector
 * decides whether anything needs ordering at all.
 *
 * `only` because these used to render on all twenty-one pages. Measured in the
 * running app: the RPA page once offered the inverse-PCR restriction-enzyme
 * chooser on an assay that is neither inverse PCR nor restriction-digested.
 */
export function BenchPanels({
  template,
  only,
  draft,
  set,
}: {
  template: string;
  only: ToolId[];
  /** Two of these panels are controls rather than references, and write here. */
  draft: Draft;
  set: (key: string, value: string) => void;
}) {
  const [checking, setChecking] = useState(false);
  if (!template.trim() || only.length === 0) return null;

  const wants = (tool: ToolId) => only.includes(tool);

  return (
    <div className="space-y-3">
      <div className="grid gap-3 lg:grid-cols-2">
        {wants("enzyme") ? (
          <EnzymePanel onRank={() => rankEnzymesAction(template, "inverse-flank")} />
        ) : null}
        {wants("cloning-tails") ? (
          <CloningTails
            draft={draft}
            set={set}
            onRank={() => rankEnzymesAction(template, "absent")}
          />
        ) : null}
        {wants("vector-primers") ? (
          <VectorPrimerPanel
            onPlace={() => placeVectorPrimersAction(template)}
            chosen={draft.vectorPrimerName}
            onChoose={(name) => set("vectorPrimerName", name)}
            own={draft.vectorPrimerSequence}
            onOwn={(sequence) => set("vectorPrimerSequence", sequence)}
            readsInto={draft.vectorPrimerReadsInto}
            onReadsInto={(side) => set("vectorPrimerReadsInto", side)}
            plasmid={draft.vectorSequence}
            onPlasmid={(sequence) => set("vectorSequence", sequence)}
          />
        ) : null}
      </div>

      {/* Behind a disclosure rather than always open: most people came here to
          design, and the ones who came to check a pair they already have know
          they did. */}
      {!wants("check-primers") ? null : checking ? (
        <CheckPrimers template={template} />
      ) : (
        <button
          type="button"
          onClick={() => setChecking(true)}
          className="min-h-6 rounded px-1 text-xs text-muted-foreground hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          Already have a pair? Check it against this sequence instead.
        </button>
      )}
    </div>
  );
}

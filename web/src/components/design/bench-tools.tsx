"use client";

/**
 * Two questions about what is already on the bench.
 *
 * Which restriction enzyme leaves the complete known inverse-PCR anchor intact,
 * and which of the universal primers in the freezer actually sit in the vector
 * being used. Neither is a
 * design; both change what a design should be, so they belong beside the
 * sequence rather than in the results.
 *
 * Both refuse to answer in the abstract. An enzyme table with no sequence is a
 * catalogue, and a primer's position in the published pUC19 is not a fact about
 * the derivative on somebody's bench — so each asks for the sequence in hand
 * and reports what it found in *that*.
 */

import { useState, useTransition } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { count } from "@/lib/numbers";
import type { EnzymeChoice, VectorPrimer } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export function EnzymePanel({
  onRank,
}: {
  /** Runs the ranking against whatever sequence the page currently holds. */
  onRank: () => Promise<{ enzymes: EnzymeChoice[]; error?: string }>;
}) {
  const [found, setFound] = useState<EnzymeChoice[] | null>(null);
  const [error, setError] = useState("");
  const [showAll, setShowAll] = useState(false);
  const [pending, start] = useTransition();

  const usable = found?.filter((entry) => entry.usable) ?? [];
  const rest = found?.filter((entry) => !entry.usable) ?? [];

  return (
    <Card className="workbench-card">
      <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle className="font-serif text-base font-semibold">
          Which enzyme leaves the anchor intact?
        </CardTitle>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={pending}
          onClick={() =>
            start(async () => {
              setError("");
              const answer = await onRank();
              if (answer.error) setError(answer.error);
              else setFound(answer.enzymes);
            })
          }
        >
          {pending ? "Looking…" : found ? "Look again" : "Look"}
        </Button>
      </CardHeader>

      <CardContent className="space-y-3">
        {error ? <p className="text-xs text-destructive">{error}</p> : null}

        {found === null ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            Standard two-flank inverse PCR needs a restriction enzyme with no recognition site
            inside the complete known anchor. The digest sites that bound the recoverable fragment
            lie in the unknown flanking DNA; after self-ligation that one fragment carries the
            intact anchor and both flanks. This checks the sequence above against PCRStudio’s
            built-in enzyme catalogue subset; it is not an exhaustive supplier catalogue.
          </p>
        ) : (
          <>
            <EnzymeList entries={usable} />
            {usable.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                None of the enzymes in PCRStudio’s built-in catalogue subset leaves the complete
                known anchor uncut.
              </p>
            ) : null}

            {rest.length > 0 ? (
              <button
                type="button"
                onClick={() => setShowAll((open) => !open)}
                className="inline-flex min-h-6 items-center rounded px-1 text-xs text-muted-foreground hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              >
                {showAll ? "Hide" : `Show the other ${rest.length}`}
              </button>
            ) : null}
            {showAll ? <EnzymeList entries={rest} /> : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function EnzymeList({ entries }: { entries: EnzymeChoice[] }) {
  if (entries.length === 0) return null;

  return (
    <ul className="space-y-1.5">
      {entries.map((entry) => (
        <li key={entry.enzyme} className="space-y-0.5">
          <div className="flex flex-wrap items-baseline gap-x-3 text-xs">
            <span className={cn("font-medium", !entry.usable && "text-muted-foreground")}>
              {entry.enzyme}
            </span>
            <code className="font-mono text-muted-foreground">{entry.site}</code>
            {entry.expected_fragment ? (
              <span className="text-muted-foreground tabular-nums">
                fragment about {count(entry.expected_fragment.mean_at_a_random_base)} bp
              </span>
            ) : null}
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground">
            {entry.why}
            {entry.usable && !entry.expected_fragment
              ? " The restriction-fragment/circle size cannot be derived from the intact known anchor alone — it depends on where this enzyme cuts in the unknown flanking DNA."
              : ""}
          </p>
        </li>
      ))}
    </ul>
  );
}

export function VectorPrimerPanel({
  onPlace,
  chosen,
  onChoose,
  own,
  onOwn,
  readsInto,
  onReadsInto,
  plasmid,
  onPlasmid,
}: {
  /** Places the universal primers in whatever vector the page holds. */
  onPlace: () => Promise<{
    primers: VectorPrimer[];
    checkedAgainst: string;
    note: string;
    error?: string;
  }>;
  /**
   * The primer this design will be partnered against, if one was picked.
   *
   * The panel used to be a reference only: it listed what was in the vector
   * and stopped there, while the engine's `vectorPrimer` field and the
   * worker's backbone screen sat unreachable. Screening a colony with two
   * primers inside the insert gives the same band whichever way round it went
   * in, so pairing against a primer in the backbone is the only way this assay
   * answers the question it exists to answer.
   */
  chosen?: string;
  onChoose?: (name: string) => void;
  /** A primer this build has never heard of, given by sequence. */
  own?: string;
  onOwn?: (sequence: string) => void;
  /** Which end of the insert the vector primer approaches from. */
  readsInto?: string;
  onReadsInto?: (side: string) => void;
  /** The plasmid, linearised where the insert goes in. */
  plasmid?: string;
  onPlasmid?: (sequence: string) => void;
}) {
  const [found, setFound] = useState<{
    primers: VectorPrimer[];
    checkedAgainst: string;
    note: string;
  } | null>(null);
  const [error, setError] = useState("");
  const [showAll, setShowAll] = useState(false);
  const [pending, start] = useTransition();

  const usable = found?.primers.filter((primer) => primer.usable) ?? [];
  const rest = found?.primers.filter((primer) => !primer.usable) ?? [];

  return (
    <Card className="workbench-card">
      <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle className="font-serif text-base font-semibold">
          Primers you already have
        </CardTitle>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={pending}
          onClick={() =>
            start(async () => {
              setError("");
              const answer = await onPlace();
              if (answer.error) setError(answer.error);
              else setFound(answer);
            })
          }
        >
          {pending ? "Checking…" : found ? "Check again" : "Check"}
        </Button>
      </CardHeader>

      <CardContent className="space-y-3">
        {error ? <p className="text-xs text-destructive">{error}</p> : null}

        {found === null ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            Screening a colony usually means using a primer already in the freezer rather than
            ordering one. This places the universal primers in the vector above — not in the
            published plasmid, because the one on your bench is rarely the one in the catalogue.
          </p>
        ) : (
          <>
            <p className="text-xs leading-relaxed text-muted-foreground">{found.note}</p>
            <PrimerList primers={usable} chosen={chosen} onChoose={onChoose} />
            {rest.length > 0 ? (
              <button
                type="button"
                onClick={() => setShowAll((open) => !open)}
                className="inline-flex min-h-6 items-center rounded px-1 text-xs text-muted-foreground hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              >
                {showAll ? "Hide" : `Show the ${rest.length} that will not work here`}
              </button>
            ) : null}
            {showAll ? <PrimerList primers={rest} chosen={chosen} onChoose={onChoose} /> : null}
          </>
        )}

        {onChoose ? (
          <div className="space-y-2 border-t pt-3">
            {/*
             * A cloning bench is full of primers that predate any catalogue,
             * and the engine has always allowed one to be given by sequence.
             * The panel could only pick from the list, so anybody screening
             * with an in-house primer had no way to use this assay at all.
             */}
            <div className="space-y-1">
              <Label htmlFor="vectorPrimerSequence" className="text-xs">
                Or a primer of your own
              </Label>
              <Input
                id="vectorPrimerSequence"
                value={own ?? ""}
                onChange={(event) => onOwn?.(event.target.value.toUpperCase())}
                placeholder="the bases, if it is not in the list"
                className="font-mono text-xs"
              />
            </div>

            {/*
             * The plasmid itself, which buys the one number this screen could
             * never give: every result it produced reported its product as
             * unknown, because the distance from the vector primer to the
             * cloning site belongs to a molecule nothing here had seen.
             *
             * Linearised where the insert goes in — the molecule they had in
             * their hand before the ligation — so nothing has to be assumed
             * about where a file begins.
             */}
            <div className="space-y-1">
              <Label htmlFor="vectorSequence" className="text-xs">
                The vector, linearised where the insert goes in
              </Label>
              <textarea
                id="vectorSequence"
                value={plasmid ?? ""}
                onChange={(event) => onPlasmid?.(event.target.value)}
                rows={3}
                placeholder="Optional. Paste it and the result gives the product size instead of half of it."
                className="w-full rounded-lg border border-border/70 bg-surface-wash/35 px-3 py-2 font-mono text-xs focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              />
              <p className="text-xs leading-relaxed text-muted-foreground">
                Without it the result can only say how far the insert primer sits from the end of
                the insert. The rest is however far your vector primer sits from the cloning site,
                which is a property of your plasmid.
              </p>
            </div>

            <div className="space-y-1">
              <Label htmlFor="vectorPrimerReadsInto" className="text-xs">
                Which end of the insert it reads towards
              </Label>
              <select
                id="vectorPrimerReadsInto"
                value={readsInto || "start"}
                onChange={(event) => onReadsInto?.(event.target.value)}
                className="h-9 w-full rounded-lg border border-border/70 bg-surface-wash/35 px-3 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              >
                <option value="start">
                  The beginning — the primer designed here reads back to it
                </option>
                <option value="end">The end — the design reads the other way</option>
              </select>
              <p className="text-xs leading-relaxed text-muted-foreground">
                This is what makes the screen answer the orientation question. Get it backwards and
                every colony reads as empty.
              </p>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function PrimerList({
  primers,
  chosen,
  onChoose,
}: {
  primers: VectorPrimer[];
  chosen?: string;
  onChoose?: (name: string) => void;
  /** A primer this build has never heard of, given by sequence. */
  own?: string;
  onOwn?: (sequence: string) => void;
  /** Which end of the insert the vector primer approaches from. */
  readsInto?: string;
  onReadsInto?: (side: string) => void;
  /** The plasmid, linearised where the insert goes in. */
  plasmid?: string;
  onPlasmid?: (sequence: string) => void;
}) {
  if (primers.length === 0) return null;

  return (
    <ul className="space-y-1.5">
      {primers.map((primer) => (
        <li key={primer.name} className="space-y-0.5">
          <div className="flex flex-wrap items-baseline gap-x-3 text-xs">
            {/* Radio rather than a button: one partner, and picking a second
                un-picks the first, which is what the reaction does too. */}
            {onChoose ? (
              <label className="flex items-center gap-1.5">
                <input
                  type="radio"
                  name="vectorPrimerName"
                  checked={chosen === primer.name}
                  onChange={() => onChoose(primer.name)}
                  className="size-3 accent-primary"
                />
                <span className={cn("font-medium", !primer.usable && "text-muted-foreground")}>
                  {primer.name}
                </span>
              </label>
            ) : (
              <span className={cn("font-medium", !primer.usable && "text-muted-foreground")}>
                {primer.name}
              </span>
            )}
            <code className="font-mono text-muted-foreground">{primer.sequence}</code>
            <span className="text-muted-foreground tabular-nums">
              {primer.tm} °C
              {primer.at !== null && primer.at !== undefined ? ` · at ${count(primer.at)}` : ""}
            </span>
          </div>
          {primer.why ? (
            <p className="text-xs leading-relaxed text-muted-foreground">
              {primer.why}
              {primer.usable && primer.tm < 57
                ? " Cooler than an ordinary design window, so a partner for it has to be designed down to it rather than to the default."
                : ""}
            </p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

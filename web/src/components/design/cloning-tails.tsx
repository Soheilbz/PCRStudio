"use client";

import { useState, useTransition } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import type { EnzymeChoice } from "@/lib/api/types";

/**
 * Which sites go on the two primer ends, and how much sits outside them.
 *
 * This is a control rather than a reference: the engine has carried a `tails`
 * field since it was written, the worker builds and checks the tails, and no
 * page could reach either — so the one assay that exists to add restriction
 * sites was designing bare primers and leaving somebody to paste the sites on
 * by hand.
 *
 * It asks the opposite question to the panel on the inverse PCR page, which is
 * why it is a separate component and not a flag on that one. Cloning needs
 * enzymes that are *absent* from the insert; a site inside the fragment means
 * the digest opens the middle as well as the ends. The cloning page used to be
 * shown the inverse-PCR ranking, headed "Which enzyme opens this once?", and
 * the enzymes at the top of that list are exactly the ones to avoid here.
 */
export function CloningTails({
  draft,
  set,
  onRank,
}: {
  draft: Record<string, string>;
  set: (key: string, value: string) => void;
  /** Ranks the catalogue against whatever sequence the page currently holds. */
  onRank: () => Promise<{ enzymes: EnzymeChoice[]; error?: string }>;
}) {
  const [found, setFound] = useState<EnzymeChoice[] | null>(null);
  const [error, setError] = useState("");
  const [pending, start] = useTransition();

  const safe = found?.filter((entry) => entry.usable) ?? [];
  const cutting = found?.filter((entry) => !entry.usable) ?? [];
  const forward = draft.forwardEnzyme ?? "";
  const reverse = draft.reverseEnzyme ?? "";

  /** The one mistake this design cannot recover from. */
  const sameBothEnds = forward !== "" && forward === reverse;

  return (
    <Card className="workbench-card">
      <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle className="font-serif text-base font-semibold">
          Which sites go on the ends?
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
          {pending ? "Checking…" : found ? "Check again" : "Check the insert"}
        </Button>
      </CardHeader>

      <CardContent className="space-y-3">
        {error ? <p className="text-xs text-destructive">{error}</p> : null}

        <p className="text-xs leading-relaxed text-muted-foreground">
          An enzyme whose site occurs inside the insert cuts the product in the middle as well as at
          its ends, and what goes into the vector is a fragment of what you wanted. Checking the
          insert lists the enzymes in PCRStudio’s built-in catalogue subset that are absent from it;
          this is not an exhaustive restriction-enzyme catalogue.
        </p>

        <div className="grid gap-3 sm:grid-cols-2">
          <Choice
            id="cloning-forward-enzyme"
            label="Forward end"
            value={forward}
            onChange={(next) => set("forwardEnzyme", next)}
            safe={safe}
            cutting={cutting}
          />
          <Choice
            id="cloning-reverse-enzyme"
            label="Reverse end"
            value={reverse}
            onChange={(next) => set("reverseEnzyme", next)}
            safe={safe}
            cutting={cutting}
          />
        </div>

        {sameBothEnds ? (
          <div className="rounded-lg border border-warning/35 bg-warning/5 px-3 py-2 text-xs leading-relaxed text-warning">
            Both ends carry {forward}. PCRStudio will treat this as a valid{" "}
            <strong>non-directional</strong>
            cloning branch rather than reject it. Plan a vector-only/background control, vector
            dephosphorylation when appropriate, and an orientation screen (colony PCR, digest or
            sequencing) because identical ends do not encode insert direction.
          </div>
        ) : null}

        <div className="space-y-1.5">
          <Label htmlFor="tailProtocol" className="text-xs">
            End-cleavage authority
          </Label>
          <select
            id="tailProtocol"
            required
            value={draft.tailProtocol ?? "neb-general-6bp"}
            onChange={(event) => set("tailProtocol", event.target.value)}
            className="h-9 w-full rounded-lg border border-border/70 bg-surface-wash/35 px-3 text-sm sm:max-w-md"
          >
            <option value="neb-general-6bp">NEB cleavage-close-to-end general rule — 6 bp</option>
          </select>
          <input type="hidden" name="protectiveBases" value="6" />
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="forwardProtectiveSequence" className="text-xs">
                Forward protective sequence
              </Label>
              <input
                id="forwardProtectiveSequence"
                name="forwardProtectiveSequence"
                required={forward !== "" && reverse !== ""}
                maxLength={6}
                minLength={6}
                pattern="[ACGTacgt]{6}"
                value={draft.forwardProtectiveSequence ?? ""}
                onChange={(event) =>
                  set("forwardProtectiveSequence", event.target.value.toUpperCase())
                }
                placeholder="6 explicit bases"
                className="h-9 w-full rounded-lg border border-border/70 bg-surface-wash/35 px-3 font-mono text-sm"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="reverseProtectiveSequence" className="text-xs">
                Reverse protective sequence
              </Label>
              <input
                id="reverseProtectiveSequence"
                name="reverseProtectiveSequence"
                required={forward !== "" && reverse !== ""}
                maxLength={6}
                minLength={6}
                pattern="[ACGTacgt]{6}"
                value={draft.reverseProtectiveSequence ?? ""}
                onChange={(event) =>
                  set("reverseProtectiveSequence", event.target.value.toUpperCase())
                }
                placeholder="6 explicit bases"
                className="h-9 w-full rounded-lg border border-border/70 bg-surface-wash/35 px-3 font-mono text-sm"
              />
            </div>
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground">
            Scientific-Strict locks this named branch to six flanking bases outside each site, but
            it does not invent their sequence. NEB gives the six-base rule and says the added bases
            should avoid palindromes and primer dimers; enter the exact DNA you intend to order. The
            enzyme table’s first non-zero activity point is descriptive evidence, not an efficiency
            recommendation.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

function Choice({
  id,
  label,
  value,
  onChange,
  safe,
  cutting,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (next: string) => void;
  safe: EnzymeChoice[];
  cutting: EnzymeChoice[];
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} className="text-xs">
        {label}
      </Label>
      <select
        id={id}
        aria-label={label}
        required
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-9 w-full rounded-lg border border-border/70 bg-surface-wash/35 px-3 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        <option value="">Choose a restriction site</option>
        {safe.length > 0 ? (
          <optgroup label="Absent from the insert">
            {safe.map((entry) => (
              <option key={entry.enzyme} value={entry.enzyme}>
                {entry.enzyme} · {entry.site}
              </option>
            ))}
          </optgroup>
        ) : null}
        {/*
         * Listed, not hidden. Somebody with a vector cut by only one enzyme
         * needs to see that their enzyme is the problem, rather than to find
         * it missing from a list with no explanation.
         */}
        {cutting.length > 0 ? (
          <optgroup label="Cuts the insert — not usable here">
            {cutting.map((entry) => (
              <option key={entry.enzyme} value={entry.enzyme}>
                {entry.enzyme} · {entry.site} · cuts {entry.cuts_inside.length}×
              </option>
            ))}
          </optgroup>
        ) : null}
      </select>
    </div>
  );
}

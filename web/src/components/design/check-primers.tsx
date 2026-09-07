"use client";

/**
 * The question a design tool is not usually asked.
 *
 * Somebody has a pair — from a paper, from a predecessor's notebook, from a
 * kit — and is about to spend a week on it. Nobody is going to redesign them.
 * What they want to know is whether the primers are any good, and against what.
 *
 * So nothing here is a score and nothing is ranked: one pair is not a choice.
 * Every measurement is shown beside the window a designed primer would have
 * been held to, and being outside that window is reported as being outside a
 * window somebody chose for a different reaction, not as a fault. The M13
 * pair, which half the world uses, sits outside the default window on both
 * primers.
 */

import { useState, useTransition } from "react";

import { FieldGroup } from "@/components/form-parts";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { maybeCount } from "@/lib/numbers";
import type { CheckedPair, CheckMeasurement } from "@/lib/api/types";
import { checkPrimersAction } from "@/lib/projects/actions";
import { cn } from "@/lib/utils";
import { nucleotideSequenceForCase } from "@/components/design/approximate-bases";

const MODULE_LABELS: Record<string, string> = {
  "standard-pcr": "Standard PCR",
  "long-range-pcr": "Long-range PCR",
  "colony-pcr": "Colony PCR",
  "qpcr-sybr": "dye-qPCR",
  "digital-pcr": "dye/EvaGreen digital PCR",
  rpa: "RPA",
};

export function CheckPrimers({
  template,
  moduleId,
  lowercaseMasking: declaredLowercaseMasking,
}: {
  template: string;
  moduleId?: string;
  lowercaseMasking?: boolean;
}) {
  const [left, setLeft] = useState("");
  const [right, setRight] = useState("");
  const [background, setBackground] = useState("");
  const [lowercaseMasking, setLowercaseMasking] = useState<boolean | null>(
    declaredLowercaseMasking ?? null,
  );
  const [maxMismatches, setMaxMismatches] = useState("3");
  const [result, setResult] = useState<CheckedPair | null>(null);
  const [error, setError] = useState("");
  const [pending, start] = useTransition();

  const hasLowercaseNucleotide = /[acgturyswkmbdhvn]/.test(nucleotideSequenceForCase(template));
  const ready =
    left.trim() &&
    right.trim() &&
    template.trim() &&
    (!hasLowercaseNucleotide || lowercaseMasking !== null);

  return (
    <div className="space-y-5">
      <Card className="workbench-card">
        <CardHeader>
          <CardTitle className="font-serif text-base font-semibold">
            {moduleId
              ? `Evaluate this existing pair as ${MODULE_LABELS[moduleId] ?? moduleId}`
              : "The pair you already have"}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="check-forward-primer" className="text-xs">
                Forward
              </Label>
              <Input
                id="check-forward-primer"
                aria-label="Forward primer"
                value={left}
                onChange={(event) => setLeft(event.target.value)}
                placeholder="GTAAAACGACGGCCAGT"
                className="font-mono"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="check-reverse-primer" className="text-xs">
                Reverse
              </Label>
              <Input
                id="check-reverse-primer"
                aria-label="Reverse primer"
                value={right}
                onChange={(event) => setRight(event.target.value)}
                placeholder="CAGGAAACAGCTATGAC"
                className="font-mono"
              />
            </div>
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground">
            Which is which is read from the strand each one sits on, so pasting them the other way
            round gives the same answer. Both are checked against the sequence above — a primer
            against the wrong template measures exactly as well as one against the right template,
            right up until the reaction produces nothing.
          </p>

          {hasLowercaseNucleotide ? (
            <FieldGroup
              label="Meaning of lowercase template bases"
              className="rounded-md border p-3"
            >
              <p className="text-xs leading-relaxed text-muted-foreground">
                Required. PCRStudio does not infer repeat masking from how much of the sequence is
                lowercase.
              </p>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant={lowercaseMasking === true ? "default" : "outline"}
                  onClick={() => setLowercaseMasking(true)}
                >
                  Intentional soft masking
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant={lowercaseMasking === false ? "default" : "outline"}
                  onClick={() => setLowercaseMasking(false)}
                >
                  Formatting only
                </Button>
              </div>
            </FieldGroup>
          ) : null}

          <div className="space-y-1.5">
            <Label htmlFor="check-background-sequence" className="text-xs">
              Anything they must not also amplify
            </Label>
            <Textarea
              id="check-background-sequence"
              aria-label="Background sequence"
              value={background}
              onChange={(event) => setBackground(event.target.value)}
              placeholder="Optional. A genome, a plasmid, the relatives you need to be distinguished from…"
              className="min-h-20 font-mono text-xs"
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="check-max-mismatches" className="text-xs">
                Whole-primer mismatch budget
              </Label>
              <Input
                id="check-max-mismatches"
                type="number"
                min={0}
                max={20}
                value={maxMismatches}
                onChange={(event) => setMaxMismatches(event.target.value)}
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button
              type="button"
              size="sm"
              disabled={!ready || pending}
              onClick={() =>
                start(async () => {
                  setError("");
                  const parsedMaxMismatches = maxMismatches.trim()
                    ? Number(maxMismatches)
                    : undefined;
                  if (
                    parsedMaxMismatches !== undefined &&
                    (!Number.isInteger(parsedMaxMismatches) ||
                      parsedMaxMismatches < 0 ||
                      parsedMaxMismatches > 20)
                  ) {
                    setError("The mismatch tolerance must be an integer from 0 to 20.");
                    setResult(null);
                    return;
                  }
                  const answer = await checkPrimersAction({
                    moduleId,
                    template,
                    lowercaseMasking: lowercaseMasking ?? undefined,
                    left,
                    right,
                    background,
                    maxMismatches: parsedMaxMismatches,
                  });
                  if (answer.error) {
                    setError(answer.error);
                    setResult(null);
                  } else if (answer.result) {
                    setResult(answer.result);
                  }
                })
              }
            >
              {pending ? "Measuring…" : "Check them"}
            </Button>
            {!ready ? (
              <p className="text-xs text-muted-foreground">
                {!template.trim()
                  ? "Paste a sequence first."
                  : hasLowercaseNucleotide && lowercaseMasking === null
                    ? "Declare what lowercase bases mean."
                    : "Both primers, please."}
              </p>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {error ? (
        <Card className="workbench-card">
          <CardContent className="pt-6">
            <p className="text-sm leading-relaxed text-destructive">{error}</p>
          </CardContent>
        </Card>
      ) : null}

      {result ? <Answer result={result} /> : null}
    </div>
  );
}

function Answer({ result }: { result: CheckedPair }) {
  return (
    <div className="space-y-4">
      <Product result={result} />

      {(["left", "right"] as const).map((role) => {
        const primer = result.primers[role];
        if (!primer) return null;
        return (
          <Card key={role} className="workbench-card">
            <CardHeader className="pb-2">
              <CardTitle className="flex flex-wrap items-baseline justify-between gap-x-3 font-serif text-base font-semibold">
                <span>{role === "left" ? "Forward" : "Reverse"} primer</span>
                <span className="text-xs font-normal text-muted-foreground tabular-nums">
                  at base {maybeCount(primer.at)}, {primer.orientation || "not placed"}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <code className="block font-mono text-xs break-all">{primer.sequence}</code>
              <Measurements entries={primer.checks} />
            </CardContent>
          </Card>
        );
      })}

      <Card className="workbench-card">
        <CardHeader className="pb-2">
          <CardTitle className="font-serif text-base font-semibold">The two together</CardTitle>
        </CardHeader>
        <CardContent>
          <Measurements entries={result.pair.checks} />
        </CardContent>
      </Card>

      {result.off_targets.checked ? (
        <Card className="workbench-card">
          <CardHeader className="pb-2">
            <CardTitle className="font-serif text-base font-semibold">
              What else they would amplify
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-relaxed text-muted-foreground">
              {result.off_targets.note ||
                `${result.off_targets.product_count ?? 0} unwanted product(s) predicted in the background given.`}
            </p>
          </CardContent>
        </Card>
      ) : null}

      <p className="text-xs leading-relaxed text-muted-foreground">{result.note}</p>
    </div>
  );
}

function Product({ result }: { result: CheckedPair }) {
  const product = result.product;
  return (
    <Card className="workbench-card">
      <CardHeader className="pb-2">
        <CardTitle className="font-serif text-base font-semibold">
          {product.exists
            ? `They give a ${maybeCount(product.size)} bp product`
            : "They give no product on this template"}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {product.exists ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            From base {maybeCount(product.from)} to {maybeCount(product.to)}
            {product.in_range === false && product.wanted
              ? `, which is outside the ${product.wanted[0]}–${product.wanted[1]} bp the window asked for — not necessarily wrong, since that window was chosen for a different reaction.`
              : "."}
          </p>
        ) : (
          <p className="text-sm leading-relaxed text-muted-foreground">{product.note}</p>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * Every measurement beside the window it is compared against.
 *
 * Outside is drawn as different rather than as wrong, because it usually is:
 * these primers were made for somebody else's reaction, and the window is ours.
 */
function Measurements({ entries }: { entries: CheckMeasurement[] }) {
  return (
    <ul className="space-y-1.5">
      {entries.map((entry) => (
        <li key={entry.name} className="space-y-0.5">
          <div className="flex flex-wrap items-baseline gap-x-3 text-xs">
            <span className="w-full shrink-0 text-muted-foreground sm:w-40">{entry.name}</span>
            <span
              className={cn(
                "tabular-nums",
                entry.inside === false ? "text-destructive" : "text-foreground",
              )}
            >
              {entry.value} {entry.unit}
            </span>
            <span className="text-muted-foreground tabular-nums">
              {entry.inside === null || entry.wanted === null
                ? "diagnostic only — no protocol-specific pass/fail boundary supplied"
                : entry.inside
                  ? "inside the window"
                  : `${entry.off_by} ${entry.unit} outside ${entry.wanted[0]}–${entry.wanted[1]}`}
            </span>
          </div>
          {entry.detail ? (
            <p className="text-xs leading-relaxed text-muted-foreground sm:pl-40">{entry.detail}</p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

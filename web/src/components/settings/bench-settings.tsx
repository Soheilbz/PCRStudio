"use client";

import { FlaskConical } from "lucide-react";
import { useState, useTransition } from "react";

import { WrappedField } from "@/components/form-parts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { Preferences } from "@/lib/api/types";
import { savePreferencesAction } from "@/lib/auth/actions";

/**
 * What is actually on this person's bench.
 *
 * Every project asks which enzyme the reaction uses, and for most people the
 * answer is the same every time — they own one, or two. Until now it had to be
 * chosen again on every new project, from a list ordered by what the assay
 * prefers rather than by what is in the freezer.
 *
 * Deliberately narrow. The temptation with a settings page is to let somebody
 * override the design constraints too — melting temperature windows, product
 * sizes — and that would be a mistake here: those are per-assay, researched,
 * and the reason each module asks a different set of questions in the first
 * place. A global override of them would quietly turn every module back into
 * one form pretending to serve all of them.
 *
 * Stored on the account rather than in this browser, because "which enzyme I
 * own" follows the person and their lab, not the machine they happen to be
 * sitting at. That is the opposite of the theme, which is why the two are
 * separate cards saying different things about where they are kept.
 */
export function BenchSettings({
  preferences,
  polymerases,
}: {
  preferences: Preferences;
  /** Every enzyme any module offers, so the choice is not module-specific. */
  polymerases: { id: string; name: string; summary: string }[];
}) {
  const [chosen, setChosen] = useState(preferences.preferredPolymerase ?? "");
  const [said, setSaid] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [saving, save] = useTransition();

  const submit = (next: string) => {
    const previous = chosen;
    setChosen(next);
    setSaid(null);
    setFailed(null);

    save(async () => {
      const answer = await savePreferencesAction(
        // An empty choice means "no preference", which has to be sent as an
        // absence rather than an empty string — otherwise unsetting it stores
        // a preference for an enzyme with no name.
        next ? { preferredPolymerase: next } : {},
      );
      if (answer.error) {
        // The select is optimistic so the choice feels immediate, but the
        // account is the source of truth. Put the previous value back when
        // persistence fails instead of displaying a preference that was never
        // saved and will disappear on the next page load.
        setChosen(previous);
        setFailed(answer.error);
      } else {
        setSaid(next ? "Saved." : "Preference cleared.");
      }
    });
  };

  const summary = polymerases.find((entry) => entry.id === chosen)?.summary;

  return (
    <Card className="workbench-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 font-serif text-lg font-semibold">
          <FlaskConical className="size-4 text-muted-foreground" aria-hidden="true" />
          Your bench
        </CardTitle>
        <CardDescription>
          Saved to your account, so it follows you to another machine. Unlike the theme above, which
          stays in this browser.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-3">
        <WrappedField
          label="Enzyme you usually use"
          hint="The starting choice for a new project, wherever the assay offers it. It is a starting point only: every project keeps whatever was chosen in it, and changing this does not reach back into one."
        >
          <select
            value={chosen}
            disabled={saving}
            onChange={(event) => submit(event.target.value)}
            className="h-9 w-full rounded-lg border border-border/70 bg-surface-wash/35 px-3 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:opacity-60 sm:max-w-sm"
          >
            <option value="">No preference — let each assay choose</option>
            {polymerases.map((entry) => (
              <option key={entry.id} value={entry.id}>
                {entry.name}
              </option>
            ))}
          </select>
        </WrappedField>

        {summary ? (
          <p className="text-xs leading-relaxed text-muted-foreground">{summary}</p>
        ) : null}

        {said ? (
          <p role="status" className="text-sm text-success">
            {said}
          </p>
        ) : null}
        {failed ? (
          <p role="alert" className="text-sm text-destructive">
            {failed}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

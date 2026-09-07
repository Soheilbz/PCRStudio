"use client";

import { ArrowRight, SearchX, Search, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useDeferredValue, useMemo } from "react";

import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { STATUS_LABELS } from "@/lib/api/labels";
import type { Goal, GoalDescription, ModuleManifest, ModuleStatus } from "@/lib/api/types";

const STATUS_ORDER: ModuleStatus[] = ["stable", "experimental", "planned"];

function matches(module: ModuleManifest, needle: string): boolean {
  if (!needle) return true;
  const haystack = `${module.name} ${module.id} ${module.summary}`.toLowerCase();
  // Every word has to appear somewhere, in any order, so "probe qpcr" works.
  return needle
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((word) => haystack.includes(word));
}

export function ModuleBrowser({
  modules,
  goals,
}: {
  modules: ModuleManifest[];
  goals: GoalDescription[];
}) {
  /*
   * The filters live in the URL rather than in component state.
   *
   * A filtered list is a thing people refer to — "the genotyping modules", "the
   * ones that are still experimental" — and with the state held in the
   * component none of the ordinary ways of referring to it worked. The address
   * bar never changed, so there was nothing to send anybody, nothing to
   * bookmark, and reloading dropped the filter. The back button, which everyone
   * uses to undo a filter, left the page instead.
   *
   * How each filter enters history is decided per filter, because the two
   * kinds behave differently under Back.
   *
   * A goal or a status is one deliberate click, and Back is what people press
   * to undo one — so those are pushed. Typing is not: a search box that pushed
   * per keystroke would turn one Back press into six, and none of the six
   * intermediate spellings is a state anybody meant to be in. Those replace.
   */
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const query = params.get("q") ?? "";
  const goal = (params.get("goal") as Goal | null) ?? null;
  const status = (params.get("status") as ModuleStatus | null) ?? null;

  const setFilter = useCallback(
    (key: string, value: string | null, remember: "push" | "replace") => {
      const next = new URLSearchParams(params.toString());
      if (value) next.set(key, value);
      else next.delete(key);
      if (next.toString() === params.toString()) return;

      const search = next.toString();
      const where = search ? `${pathname}?${search}` : pathname;
      // `scroll: false` because changing a filter is not navigating: the list
      // updates in place, and yanking the page to the top loses somebody's
      // position in it.
      if (remember === "push") router.push(where, { scroll: false });
      else router.replace(where, { scroll: false });
    },
    [params, pathname, router],
  );

  // Keeps typing responsive when the list grows: the input updates every
  // keystroke while the filtered results are allowed to lag a frame.
  const deferredQuery = useDeferredValue(query);
  const isFiltered = Boolean(query || goal || status);

  const results = useMemo(
    () =>
      modules.filter(
        (module) =>
          matches(module, deferredQuery) &&
          (!goal || module.goal === goal) &&
          (!status || module.status === status),
      ),
    [modules, deferredQuery, goal, status],
  );

  const groups = useMemo(
    () =>
      goals
        .map((entry) => ({
          goal: entry,
          modules: results.filter((module) => module.goal === entry.id),
        }))
        .filter((group) => group.modules.length > 0),
    [results, goals],
  );

  const availableGoals = useMemo(
    () => goals.filter((entry) => modules.some((module) => module.goal === entry.id)),
    [modules, goals],
  );

  // Also pushed: somebody who clears by accident should get it back.
  const clear = () => router.push(pathname, { scroll: false });

  return (
    <div className="space-y-4">
      <div className="workbench-card space-y-2.5 rounded-xl border bg-surface-wash/45 p-3 sm:p-4">
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            value={query}
            onChange={(event) => setFilter("q", event.target.value, "replace")}
            placeholder="Search by name, identifier or description…"
            aria-label="Search modules"
            className="pl-9"
          />
        </div>

        <div className="flex flex-wrap items-center gap-x-2 gap-y-2">
          <Filters
            label="Goal"
            options={availableGoals.map((entry) => ({ value: entry.id, label: entry.label }))}
            selected={goal}
            onSelect={(value) => setFilter("goal", value, "push")}
          />
          <span className="mx-1 hidden h-4 w-px bg-border sm:block" aria-hidden="true" />
          <Filters
            label="Status"
            options={STATUS_ORDER.filter((entry) =>
              modules.some((module) => module.status === entry),
            ).map((entry) => ({ value: entry, label: STATUS_LABELS[entry] }))}
            selected={status}
            onSelect={(value) => setFilter("status", value, "push")}
          />
          {isFiltered ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={clear}
              // Beside the filters the word "Clear" is unambiguous; in a screen
              // reader's list of buttons it is a verb with no object. The empty
              // state's version of this button already said "Clear filters", so
              // the two also stop announcing themselves differently for doing
              // the same thing.
              aria-label="Clear filters"
              className="h-7 px-2 text-muted-foreground"
            >
              <X className="size-3.5" />
              Clear
            </Button>
          ) : null}
        </div>
      </div>

      <p className="text-xs text-muted-foreground" aria-live="polite">
        {results.length} of {modules.length} modules
      </p>

      {results.length === 0 ? (
        <EmptyState
          icon={SearchX}
          title="No module matches those filters"
          description="Try a broader search, or clear the filters to see everything the core registered."
          action={
            <Button variant="outline" size="sm" onClick={clear}>
              Clear filters
            </Button>
          }
        />
      ) : (
        <div className="space-y-8">
          {groups.map(({ goal: entry, modules: grouped }) => (
            <section key={entry.id} className="space-y-3">
              <div className="flex items-center gap-2.5 rounded-r-lg border-l-2 border-primary/45 bg-surface-warm/20 px-3 py-2">
                <h2 className="font-serif text-lg tracking-tight">{entry.label}</h2>
                <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary tabular-nums">
                  {grouped.length}
                </span>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                {grouped.map((module) => (
                  <ModuleRow key={module.id} module={module} />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

function Filters<T extends string>({
  label,
  options,
  selected,
  onSelect,
}: {
  label: string;
  options: { value: T; label: string }[];
  selected: T | null;
  onSelect: (value: T | null) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label={label}>
      <span className="mr-0.5 text-xs text-muted-foreground" aria-hidden="true">
        {label}
      </span>
      {options.map(({ value, label: optionLabel }) => {
        const active = selected === value;
        return (
          <button
            key={value}
            type="button"
            aria-pressed={active}
            onClick={() => onSelect(active ? null : value)}
            className={cn(
              "rounded-full border px-2.5 py-1 text-xs transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
              active
                ? "border-primary bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-surface-warm/45 hover:text-foreground",
            )}
          >
            {optionLabel}
          </button>
        );
      })}
    </div>
  );
}

function ModuleRow({ module }: { module: ModuleManifest }) {
  /*
   * The whole card is the link: the anchor paints an `after` overlay across the
   * card, so one tab stop and one click target cover the whole surface while
   * the badge and the identifier stay out of the link's accessible name.
   */
  return (
    <Card className="workbench-card group relative h-full rounded-xl border bg-surface-wash/45 p-0 transition-[border-color,box-shadow,transform] duration-150 focus-within:border-primary/50 hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-md has-[a:focus-visible]:border-primary/50 has-[a:focus-visible]:ring-2 has-[a:focus-visible]:ring-ring">
      <div className="flex h-full flex-col gap-2 p-4 md:p-5">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <CardTitle className="font-serif text-lg font-semibold tracking-tight text-foreground transition-colors duration-150 group-hover:text-primary">
            <Link
              href={`/modules/${module.id}`}
              className="after:absolute after:inset-0 focus-visible:outline-none"
            >
              {module.name}
            </Link>
          </CardTitle>
        </div>

        <p className="text-sm leading-relaxed text-muted-foreground">{module.summary}</p>

        <div className="mt-auto flex items-center justify-between gap-3 pt-2">
          {/* Kept for the search box (which matches on it) but demoted to a
              whisper at the bottom edge; it is plumbing, not a headline. */}
          <span className="truncate font-mono text-xs text-muted-foreground/60">{module.id}</span>
          <span
            aria-hidden="true"
            className="flex shrink-0 items-center gap-1 text-xs font-medium text-primary opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-has-[a:focus-visible]:opacity-100"
          >
            Open
            <ArrowRight className="size-3 transition-transform duration-150 group-hover:translate-x-0.5" />
          </span>
        </div>
      </div>
    </Card>
  );
}

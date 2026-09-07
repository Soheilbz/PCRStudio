"use client";

import { X } from "lucide-react";
import Link from "next/link";
import { useSyncExternalStore } from "react";

const STORAGE_KEY = "pcr-studio.onboarding-dismissed";

/*
 * Read through `useSyncExternalStore` rather than an effect, so the very first
 * render already knows the answer: the server snapshot says dismissed, which
 * means nobody who closed the card ever sees it flicker back.
 */
const listeners = new Set<() => void>();

function subscribe(onChange: () => void): () => void {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
}

function isDismissed(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) !== null;
  } catch {
    // Storage can be refused (private modes, hardened browsers). The card
    // shows again on the next visit — mildly annoying, and nothing worse.
    return false;
  }
}

/** The server holds no localStorage, so from there the card counts as gone. */
const dismissedOnServer = () => true;

/**
 * Three steps to a first design, shown while the project list is still empty.
 *
 * Kept in localStorage rather than account preferences: preferences are for how
 * somebody works, and this is only whether they have been shown one card —
 * spending a backend field on it would make it harder to change the wording.
 * Dismissal is forever, which is also what keeps it quiet: nobody who has
 * already started wants the tour again, and somebody who has not can follow
 * step one and never see the card twice.
 */
export function OnboardingCard() {
  const dismissed = useSyncExternalStore(subscribe, isDismissed, dismissedOnServer);

  if (dismissed) return null;

  const dismiss = () => {
    try {
      window.localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      // Nothing to save it with; hiding it for this page at least.
    }
    for (const listener of listeners) listener();
  };

  return (
    <aside
      aria-label="Getting started"
      className="workbench-hero relative rounded-xl border border-border/70 p-4 shadow-sm"
    >
      <button
        type="button"
        onClick={dismiss}
        aria-label="Dismiss getting started"
        className="absolute top-2.5 right-2.5 inline-flex size-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-surface-warm/45 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        <X className="size-3.5" />
      </button>

      <h2 className="font-serif text-lg font-semibold tracking-tight">
        Three steps to your first design
      </h2>
      <ol className="mt-2 space-y-1.5 text-sm leading-relaxed">
        <li className="flex gap-2">
          <span className="font-medium text-primary tabular-nums">1.</span>
          <span>
            Pick an assay from{" "}
            <Link href="/modules" className="underline hover:text-foreground">
              the sidebar
            </Link>
            .
          </span>
        </li>
        <li className="flex gap-2">
          <span className="font-medium text-primary tabular-nums">2.</span>
          <span>
            Paste your template and run a design in{" "}
            <Link href="/try" className="underline hover:text-foreground">
              Try it
            </Link>
            .
          </span>
        </li>
        <li className="flex gap-2">
          <span className="font-medium text-primary tabular-nums">3.</span>
          <span>Save it here and order the oligos.</span>
        </li>
      </ol>
    </aside>
  );
}

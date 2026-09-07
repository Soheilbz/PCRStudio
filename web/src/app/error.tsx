"use client";

import { RotateCcw, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";

/**
 * Root-segment fallback for surfaces outside the authenticated workbench
 * (notably sign-in/recovery and Try it). Expected API/form failures are handled
 * closer to the control; this boundary is deliberately generic so an
 * unexpected implementation error is not reflected into the page.
 */
export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="mx-auto flex min-h-[60vh] w-full max-w-xl items-center px-5 py-12">
      <section className="w-full space-y-4 rounded-xl border border-destructive/30 bg-destructive/5 p-5">
        <div className="flex items-start gap-3">
          <TriangleAlert className="mt-0.5 size-5 shrink-0 text-destructive" aria-hidden="true" />
          <div className="space-y-1">
            <h1 className="font-serif text-lg font-semibold">This page could not be rendered</h1>
            <p className="text-sm text-muted-foreground">
              An unexpected application error occurred. Try the page again or return to the
              dashboard.
            </p>
            {error.digest ? (
              <p className="font-mono text-xs text-muted-foreground">Reference: {error.digest}</p>
            ) : null}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" onClick={reset}>
            <RotateCcw />
            Try again
          </Button>
          <Button render={<Link href="/" />} variant="outline" size="sm">
            Back to the dashboard
          </Button>
        </div>
      </section>
    </main>
  );
}

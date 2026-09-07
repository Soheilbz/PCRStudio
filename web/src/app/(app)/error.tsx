"use client";

import { RotateCcw, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

/**
 * Catches a render failure in any page below the root layout, so the shell
 * survives and the visitor keeps their navigation.
 */
export default function ErrorBoundary({
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
    <div className="space-y-6 py-4">
      <Alert variant="destructive" className="rounded-xl border-destructive/30 bg-destructive/5">
        <TriangleAlert />
        <AlertTitle className="font-serif text-base font-semibold">
          This page could not be rendered
        </AlertTitle>
        <AlertDescription>
          <p>
            An unexpected application error occurred. Try the page again or return to the dashboard.
          </p>
          {error.digest ? (
            <p className="font-mono text-xs opacity-80">Reference: {error.digest}</p>
          ) : null}
        </AlertDescription>
      </Alert>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" onClick={reset}>
          <RotateCcw />
          Try again
        </Button>
        <Button render={<Link href="/" />} variant="outline" size="sm">
          Back to the dashboard
        </Button>
      </div>
    </div>
  );
}

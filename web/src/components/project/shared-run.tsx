"use client";

import { ArrowRight, BookmarkPlus, Loader2, Share2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { ResultView } from "@/components/design/result-view";
import { LocalTime } from "@/components/local-time";
import { CopyReportButton } from "@/components/project/copy-report";
import { Button } from "@/components/ui/button";
import { forkSharedRunAction } from "@/lib/projects/actions";
import { engineLabel } from "@/lib/projects/comparison";
import type { SharedRun as SharedRunPayload } from "@/lib/api/types";

/**
 * A result somebody sent you, with an option to import / fork into your projects.
 */
export function SharedRun({
  run,
  token,
  signedIn = false,
}: {
  run: SharedRunPayload;
  token?: string;
  signedIn?: boolean;
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const handleFork = () => {
    if (!token) return;
    startTransition(async () => {
      setError(null);
      const res = await forkSharedRunAction(token);
      if (res.error) {
        setError(res.error);
        return;
      }
      if (res.projectId) {
        router.push(`/projects/${res.projectId}`);
      }
    });
  };

  return (
    <div className="space-y-5">
      <div className="workbench-hero flex flex-wrap items-start justify-between gap-3 rounded-2xl border border-border/70 p-5 shadow-sm sm:p-6">
        <div className="min-w-0 space-y-1">
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Share2 className="size-3.5" aria-hidden="true" />
            Shared with you
          </p>
          <h1 className="font-serif text-2xl font-semibold tracking-tight text-balance sm:text-3xl">
            {run.label || "A primer design"}
          </h1>
          <p className="text-sm text-muted-foreground">
            Designed <LocalTime iso={run.createdAt} relative />.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* The result is the one thing a recipient cannot take away by forking
              — this is how it leaves as text before the link is withdrawn. */}
          <CopyReportButton
            label={run.label || "A primer design"}
            createdAt={run.createdAt}
            moduleName={engineLabel(run.result)}
            result={run.result}
          />

          {token ? (
            signedIn ? (
              <Button type="button" size="sm" onClick={handleFork} disabled={pending}>
                {pending ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <BookmarkPlus className="size-3.5" />
                )}
                Save to My Projects
              </Button>
            ) : (
              <Button render={<Link href={`/sign-in?next=/shared/${token}`} />} size="sm">
                <BookmarkPlus className="size-3.5" />
                Sign in to save this run
              </Button>
            )
          ) : null}

          <Button render={<Link href="/try" />} variant="outline" size="sm">
            Design one of your own
            <ArrowRight className="size-3.5" />
          </Button>
        </div>
      </div>

      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}

      <div className="workbench-result space-y-4 rounded-2xl border-t border-primary/20 pt-5">
        <ResultView result={run.result} />
      </div>

      <p className="border-t pt-4 text-xs leading-relaxed text-muted-foreground">
        This is a read-only view of one result. Whoever shared it can withdraw the link at any time,
        and everything above stops being reachable when they do.
      </p>
    </div>
  );
}

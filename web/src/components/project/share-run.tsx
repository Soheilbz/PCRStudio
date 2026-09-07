"use client";

import { Check, Copy, Link2, Link2Off, Loader2 } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { copyText } from "@/lib/clipboard";
import { shareRunAction, unshareRunAction } from "@/lib/projects/actions";

/**
 * Hand one result to somebody who has no account.
 *
 * Two things this deliberately does not do.
 *
 * It does not remember the link. The token is minted once and stored only as
 * its hash, so this cannot show you a link you made last week — asking for
 * another mints a fresh one and kills the old, which is also what somebody
 * wants after sending one to the wrong person.
 *
 * It does not pretend the link is private. Anyone holding it can read the
 * result, and that is said in the same breath as the link rather than in a
 * paragraph underneath: a warning somebody has already scrolled past is a
 * warning that was not given.
 */
export function ShareRun({
  projectId,
  runId,
  sharedAlready,
}: {
  projectId: string;
  runId: string;
  /** Whether a link exists. Its value is not knowable — only that it does. */
  sharedAlready: boolean;
}) {
  const [link, setLink] = useState<string | null>(null);
  const [shared, setShared] = useState(sharedAlready);
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const [busy, act] = useTransition();

  const make = () =>
    act(async () => {
      setFailed(null);
      const answer = await shareRunAction(projectId, runId);
      if (answer.error || !answer.link) {
        setFailed(answer.error ?? "The link could not be made.");
        return;
      }
      setLink(`${window.location.origin}/shared/${answer.link}`);
      setShared(true);
    });

  const withdraw = () =>
    act(async () => {
      setFailed(null);
      const answer = await unshareRunAction(projectId, runId);
      if (answer.error) {
        setFailed(answer.error);
        return;
      }
      setLink(null);
      setShared(false);
    });

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={busy}
          onClick={make}
          aria-label={
            shared
              ? "Make a new link, which stops the old one working"
              : "Make a link to this result"
          }
        >
          {busy ? <Loader2 className="size-3.5 animate-spin" /> : <Link2 className="size-3.5" />}
          {shared ? "New link" : "Share"}
        </Button>

        {shared ? (
          <Button type="button" variant="ghost" size="sm" disabled={busy} onClick={withdraw}>
            <Link2Off className="size-3.5" />
            Withdraw
          </Button>
        ) : null}
      </div>

      {link ? (
        <div className="space-y-1.5 rounded-lg border border-primary/20 bg-surface-warm/35 p-2.5">
          <div className="flex items-center gap-2">
            <code className="min-w-0 flex-1 truncate font-mono text-xs">{link}</code>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                void copyText(link)
                  .then(() => {
                    setCopied(true);
                    toast.success("Share link copied", {
                      description: "Anyone holding it can read this result.",
                    });
                    setTimeout(() => setCopied(false), 1500);
                  })
                  .catch(() => {
                    // Clipboard access is refused on insecure origins and in
                    // some browsers. Say so rather than showing a success that
                    // did not happen.
                    toast.error("Could not reach the clipboard", {
                      description:
                        "Your browser refused the request. Select the link and copy it manually.",
                    });
                  });
              }}
            >
              {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground">
            Anyone with this link can read the result and the sequence in it. It is shown once —
            copy it now, because asking for it again makes a different one.
          </p>
        </div>
      ) : shared ? (
        <p className="text-xs leading-relaxed text-muted-foreground">
          A link to this result exists. It cannot be shown again — make a new one, which stops the
          old one working, or withdraw it.
        </p>
      ) : null}

      {failed ? (
        <p role="alert" className="text-xs text-destructive">
          {failed}
        </p>
      ) : null}
    </div>
  );
}

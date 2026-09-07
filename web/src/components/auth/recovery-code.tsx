"use client";

/**
 * A recovery code, shown the one time it can be.
 *
 * This screen has an unusual job: everything else in the interface can be
 * looked at again later, and this cannot. The code is stored hashed, exactly
 * like a password, so nobody — including whoever runs the server — can read it
 * back. If it is closed without being written down it is gone, and the account
 * it belongs to has no way back in after a forgotten password.
 *
 * So the design leans the whole way towards "you have to deal with this now":
 * the code is large and selectable, copying and downloading are both one click,
 * and moving on is gated behind an explicit acknowledgement rather than a
 * button somebody clicks past. That gate is deliberate friction — the only
 * place in this application where slowing somebody down is the point.
 *
 * What it must never do is make the code look decorative. It is not a receipt.
 */

import { Check, Copy, Download, ShieldCheck, AlertOctagon, Key } from "lucide-react";
import { useState, type ReactNode, useEffect } from "react";

import { Eyebrow, TickRule } from "@/components/auth/bench";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { copyText } from "@/lib/clipboard";

export function RecoveryCodePanel({
  code,
  heading,
  explanation,
  children,
}: {
  code: string;
  heading: string;
  /** Why this exists, in the words that fit where it is being shown. */
  explanation: string;
  /** What to do next — a link onward, or a form. */
  children?: ReactNode;
}) {
  const [copied, setCopied] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [downloaded, setDownloaded] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setMounted(true), 0);
    return () => clearTimeout(timer);
  }, []);

  // The code arrives as hyphen-separated groups; display it in that shape.
  // Chunking blindly by character count would cut groups in half and hand
  // somebody a string they cannot trust when they transcribe it later.
  const formattedCode =
    code
      .replace(/[^a-zA-Z0-9]/g, "")
      .match(/.{1,5}/g)
      ?.join("-") ?? code;

  return (
    <Card className={cn("animate-fade-in-up border-primary/40", mounted && "animate-slide-in")}>
      {/* Top accent bar */}
      <div
        className="absolute top-0 right-0 left-0 h-1 bg-gradient-to-r from-primary via-brand to-primary/50"
        aria-hidden="true"
      />

      <CardHeader className="relative z-10 space-y-3">
        <TickRule />
        <div className="space-y-1.5 text-center">
          <div className="mb-2 flex items-center justify-center gap-2">
            <div
              className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary"
              aria-hidden="true"
            >
              <ShieldCheck className="size-5" />
            </div>
            <Eyebrow>One-time — record this</Eyebrow>
          </div>
          <CardTitle className="flex items-center justify-center gap-2 font-serif text-lg font-semibold tracking-tight text-foreground sm:text-xl">
            <Key className="size-4.5 text-primary/80" aria-hidden="true" />
            {heading}
          </CardTitle>
          <p className="mx-auto max-w-prose text-start text-sm leading-relaxed text-muted-foreground">
            {explanation}
          </p>
        </div>
      </CardHeader>

      <CardContent className="space-y-4 pt-2">
        {/* Recovery code display */}
        <div className="animate-fade-in-up relative" style={{ animationDelay: "100ms" }}>
          <div
            className="absolute inset-0 rounded-xl bg-gradient-to-br from-primary/5 via-transparent to-brand/5"
            aria-hidden="true"
          />
          <div className="relative rounded-xl border-2 border-primary/20 bg-surface-wash/55 p-5 ring-1 ring-primary/10 sm:p-6">
            <p
              data-testid="recovery-code"
              className="text-center font-mono text-lg tracking-widest break-all text-foreground select-all sm:text-xl"
              style={{ letterSpacing: "0.3em" }}
            >
              <span className="relative z-10">{formattedCode}</span>
            </p>
            <div
              className="pointer-events-none absolute inset-0 rounded-xl bg-gradient-to-t from-background/50 to-transparent"
              aria-hidden="true"
            />
          </div>
        </div>

        {/* Action buttons */}
        <div
          className="animate-fade-in-up flex flex-wrap gap-2"
          style={{ animationDelay: "200ms" }}
          role="group"
          aria-label="Recovery code actions"
        >
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="min-w-[140px] flex-1"
            onClick={async () => {
              try {
                await copyText(code);
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
              } catch {
                // Clipboard blocked (insecure context or permission denied) — the
                // code is still selectable via select-all; copying is convenience.
                toast.error("Could not reach the clipboard", {
                  description:
                    "Select the recovery code above and copy it manually before continuing.",
                });
              }
            }}
          >
            {copied ? (
              <>
                <Check className="size-3.5 shrink-0 text-success" aria-hidden="true" />
                <span>Copied</span>
              </>
            ) : (
              <>
                <Copy className="size-3.5 shrink-0" aria-hidden="true" />
                <span>Copy code</span>
              </>
            )}
          </Button>

          {/* A file, because a clipboard is emptied by the next thing copied
              and this is the one string that cannot be fetched again. */}
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="min-w-[140px] flex-1"
            onClick={() => {
              const contents = [
                "PCRStudio recovery code",
                "",
                code,
                "",
                "This is the only copy. It was not stored anywhere in a form",
                "anyone can read, including by whoever runs the server.",
                "",
                "Use it at /recover if you forget your password. Using it sets a",
                "new password, ends every open session, and replaces this code",
                "with a new one.",
              ].join("\n");

              const blob = new Blob([contents], { type: "text/plain" });
              const url = URL.createObjectURL(blob);
              const link = document.createElement("a");
              link.href = url;
              link.download = "pcrstudio-recovery-code.txt";
              link.click();
              // Revoke after the browser has started the download; immediate revoke
              // cancels it in some engines.
              setTimeout(() => URL.revokeObjectURL(url), 1000);
              setDownloaded(true);
              setTimeout(() => setDownloaded(false), 2000);
            }}
          >
            {downloaded ? (
              <>
                <Check className="size-3.5 shrink-0 text-success" aria-hidden="true" />
                <span>Downloaded</span>
              </>
            ) : (
              <>
                <Download className="size-3.5 shrink-0" aria-hidden="true" />
                <span>Download .txt</span>
              </>
            )}
          </Button>
        </div>

        {/* Critical warning */}
        <div className="animate-fade-in-up" style={{ animationDelay: "300ms" }} role="alert">
          <div className="flex gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-4">
            <div
              className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-destructive/10 text-destructive"
              aria-hidden="true"
            >
              <AlertOctagon className="size-4.5" />
            </div>
            <div className="min-w-0 flex-1 text-sm leading-relaxed text-destructive/90">
              <p className="mb-1 font-medium">This will not be shown again.</p>
              <p className="text-start">
                It is stored the same way your password is — hashed — so it cannot be looked up or
                resent, by us or by anybody. Without it, a forgotten password means the account and
                everything in it are gone.
              </p>
            </div>
          </div>
        </div>

        {/* Acknowledgement gate */}
        <div className="animate-fade-in-up" style={{ animationDelay: "400ms" }}>
          <div
            className={cn(
              "flex items-start gap-3 rounded-xl border p-4 transition-all duration-300",
              acknowledged
                ? "border-primary/30 bg-primary/5"
                : "border-border/50 bg-surface-wash/35",
            )}
          >
            <div className="mt-0.5 flex shrink-0">
              <input
                id="acknowledged"
                type="checkbox"
                checked={acknowledged}
                onChange={(event) => setAcknowledged(event.target.checked)}
                className="size-4.5 cursor-pointer rounded border-input accent-primary transition-colors focus-visible:ring-2 focus-visible:ring-ring/50"
                aria-describedby="acknowledged-desc"
              />
            </div>
            <div className="min-w-0 flex-1">
              <Label
                htmlFor="acknowledged"
                id="acknowledged-desc"
                className="text-sm leading-relaxed font-normal text-foreground"
              >
                <span className="font-medium">I have saved this code</span> somewhere I will still
                have it if I lose my password.
              </Label>
            </div>
          </div>
        </div>

        {/* Continue action - gated */}
        <div
          data-acknowledged={acknowledged}
          className={cn(
            "animate-fade-in-up transition-all duration-300",
            acknowledged ? "" : "pointer-events-none opacity-50",
          )}
          style={{ animationDelay: "500ms" }}
          inert={!acknowledged}
        >
          {children}
        </div>
      </CardContent>
    </Card>
  );
}

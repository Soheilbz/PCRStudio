"use client";

/**
 * Getting back into an account after a forgotten password.
 *
 * The person reading this screen is having a bad day: they are locked out of
 * their own work and they are about to find out whether they still have the
 * piece of paper. Two things follow from that.
 *
 * The wording says what will happen before it happens — the code is spent,
 * every session ends, a new code arrives — because a surprise here reads as
 * something having gone wrong on top of everything else.
 *
 * And a wrong code says so plainly, while too many wrong codes say something
 * different. Those two must not be worded alike: somebody told "that code is
 * wrong" when the account is merely shuttered concludes they have lost
 * everything, and stops trying.
 */

import Link from "next/link";
import { useActionState, useState, useEffect } from "react";

import { Eyebrow, TickRule, HelixDrift } from "@/components/auth/bench";
import { RecoveryCodePanel } from "@/components/auth/recovery-code";
import { Field, FormFeedback, SubmitButton } from "@/components/form-parts";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import { continueAfterRecoveryCodeAction, recoverAction, type FormState } from "@/lib/auth/actions";

const EMPTY: FormState = {};

export function RecoverForm() {
  const [state, formAction, pending] = useActionState(recoverAction, EMPTY);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setMounted(true), 0);
    return () => clearTimeout(timer);
  }, []);

  if (state.recoveryCode) {
    return (
      <div className="animate-fade-in-up mx-auto w-full max-w-md">
        <RecoveryCodePanel
          code={state.recoveryCode}
          heading="Save your new recovery code"
          explanation={
            "Your password is changed and you are signed in. The code you just used is " +
            "spent — this is its replacement, and it is the one that matters next time."
          }
        >
          <form action={continueAfterRecoveryCodeAction.bind(null, "/")} className="w-full">
            <Button type="submit" className="w-full">
              Continue
            </Button>
          </form>
        </RecoveryCodePanel>
      </div>
    );
  }

  return (
    <Card
      className={cn(
        "animate-fade-in-up relative mx-auto w-full max-w-md overflow-hidden",
        mounted && "animate-slide-in",
      )}
    >
      {/* Enhanced helix background with layered depth */}
      <div className="absolute inset-0 -z-20 opacity-20" aria-hidden="true">
        <HelixDrift className="h-full w-full" />
      </div>
      <div
        className="absolute inset-0 -z-10 bg-gradient-to-br from-destructive/5 via-transparent to-primary/5"
        aria-hidden="true"
      />

      {/* Top accent bar */}
      <div
        className="absolute top-0 right-0 left-0 h-1 bg-gradient-to-r from-destructive via-warning to-primary/50"
        aria-hidden="true"
      />

      <CardHeader className="space-y-3 border-b border-border/40 pb-3">
        <TickRule />
        <div className="space-y-1.5 text-center">
          <Eyebrow>PCRSTUDIO · ACCOUNT RECOVERY</Eyebrow>
          <CardTitle className="font-serif text-2xl font-semibold tracking-tight text-foreground sm:text-2xl">
            Use a recovery code
          </CardTitle>
          <CardDescription className="mx-auto max-w-[36ch] text-start text-sm leading-relaxed text-muted-foreground">
            Enter the recovery code you saved when you created your account. It is the secure,
            one-time way back in when a password reset email is not available.
          </CardDescription>
        </div>
      </CardHeader>

      <CardContent className="space-y-4 pt-4">
        {/* Rate limit warning banner */}
        {(state.errorKind === "tooManyRequests" || state.errorKind === "tooManyAttempts") && (
          <div className="animate-fade-in" role="alert">
            <Alert variant="destructive" className="border-destructive/30 bg-destructive/5 text-sm">
              <AlertCircle className="size-4 shrink-0" aria-hidden="true" />
              <AlertDescription className="flex-1">
                Too many attempts. Please wait a moment before trying again.
              </AlertDescription>
            </Alert>
          </div>
        )}

        {/* Invalid code specific guidance */}
        {state.error && state.errorKind === "invalidCredentials" && (
          <div className="animate-fade-in-up" role="alert">
            <Alert className="border-warning/30 bg-warning/5 text-sm">
              <AlertCircle className="size-4 shrink-0 text-warning" aria-hidden="true" />
              <AlertDescription className="flex-1 text-foreground">
                The recovery code doesn&apos;t match. Double-check for typos — capitals, spaces and
                hyphens don&apos;t matter. If you&apos;re sure it&apos;s correct, the code may have
                already been used (each code works only once).
              </AlertDescription>
            </Alert>
          </div>
        )}

        <form
          action={formAction}
          className="space-y-3"
          data-form-ready={mounted ? "true" : undefined}
        >
          <Field
            label="Email"
            name="email"
            type="email"
            autoComplete="email"
            required
            placeholder="you@lab.example"
          />

          <Field
            label="Recovery code"
            name="recoveryCode"
            required
            autoComplete="one-time-code"
            spellCheck={false}
            maxLength={64}
            placeholder="XXXXX-XXXXX-XXXXX-XXXXX-XXXXX"
            className="font-mono tracking-wider"
            hint="Capitals, spaces and hyphens do not matter — type it however you wrote it down."
          />

          <Field
            label="New password"
            name="newPassword"
            type="password"
            autoComplete="new-password"
            required
            minLength={10}
            maxLength={256}
            hint="Use at least 10 characters. A memorable phrase is usually stronger than a short scramble."
            showStrength
          />

          <FormFeedback state={state} />

          <div className="border-t border-border/40 pt-3">
            <SubmitButton pending={pending} className="w-full" pendingLabel="Checking…">
              Set a new password
            </SubmitButton>
          </div>
        </form>

        {/* What this does - before it happens. Collapsed by default so the
            whole form fits one screen without scrolling; the answer is one
            click away for anybody who wants it before committing. */}
        <details className="animate-fade-in-up group rounded-xl border border-primary/20 bg-primary/5 text-sm">
          <summary className="flex cursor-pointer list-none items-center gap-2 p-3.5 font-medium text-foreground [&::-webkit-details-marker]:hidden">
            <Info className="size-4 shrink-0 text-primary" aria-hidden="true" />
            What this does
          </summary>
          <div className="space-y-1 px-3.5 pb-3.5 leading-relaxed">
            <p className="text-start text-muted-foreground">
              Sets the new password, signs you in, and ends every other session — including on any
              device you are still signed in on, and including anyone else who had your old
              password.
            </p>
            <p className="text-start text-muted-foreground">
              The code you use here is spent. A new one is shown once on the next screen, and it
              will not be shown again.
            </p>
          </div>
        </details>

        <p className="text-center text-sm text-muted-foreground">
          Remembered your password?{" "}
          <Link
            href="/sign-in"
            className="font-medium text-primary underline underline-offset-4 transition-colors hover:text-primary/80"
          >
            Sign in
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}

"use client";

import Link from "next/link";
import { useActionState, useState, useEffect } from "react";

import { Eyebrow, TickRule, HelixDrift } from "@/components/auth/bench";
import { RecoveryCodePanel } from "@/components/auth/recovery-code";
import { Field, FormFeedback, SubmitButton } from "@/components/form-parts";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  continueAfterRecoveryCodeAction,
  signInAction,
  signUpAction,
  type FormState,
} from "@/lib/auth/actions";

const EMPTY: FormState = {};

/** The two refusals that mean "slow down", named by kind rather than by words in the message. */
function isRateLimited(state: FormState): boolean {
  return state.errorKind === "tooManyRequests" || state.errorKind === "tooManyAttempts";
}

export function CredentialsForm({
  mode,
  next,
  notice,
}: {
  mode: "sign-in" | "sign-up";
  next: string;
  /** Something that just happened, said once above the form. */
  notice?: string;
}) {
  const isSignUp = mode === "sign-up";
  const [state, formAction, pending] = useActionState(
    isSignUp ? signUpAction : signInAction,
    EMPTY,
  );
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setMounted(true), 0);
    return () => clearTimeout(timer);
  }, []);

  /*
   * A code came back, so the account exists and the session cookie is set.
   * The form is replaced rather than sitting underneath it: this is the only
   * moment this string is readable, and leaving a "Create account" button on
   * screen invites clicking past it.
   */
  if (state.recoveryCode) {
    return (
      <div className="animate-fade-in-up mx-auto w-full max-w-md">
        <RecoveryCodePanel
          code={state.recoveryCode}
          heading="Save your recovery code"
          explanation={
            "Your account is ready and you are signed in. Save this code somewhere safe: it is " +
            "the only way to recover access if you forget your password."
          }
        >
          <form action={continueAfterRecoveryCodeAction.bind(null, next)} className="w-full">
            <Button type="submit" className="w-full">
              Go to my workspace
            </Button>
          </form>
        </RecoveryCodePanel>
      </div>
    );
  }

  return (
    <Card
      className={cn(
        "animate-fade-in-up relative mx-auto w-full max-w-md overflow-hidden shadow-xl shadow-primary/5",
        mounted && "animate-slide-in",
      )}
    >
      {/* Enhanced helix background with layered depth */}
      <div className="absolute inset-0 -z-20 opacity-20" aria-hidden="true">
        <HelixDrift className="h-full w-full" />
      </div>
      <div
        className="absolute inset-0 -z-10 bg-gradient-to-br from-primary/5 via-transparent to-brand/5"
        aria-hidden="true"
      />

      {/* Top accent bar */}
      <div
        className="absolute top-0 right-0 left-0 h-1 bg-gradient-to-r from-primary via-brand to-primary/50"
        aria-hidden="true"
      />

      <CardHeader className="space-y-3 border-b border-border/40 pb-3">
        <TickRule />
        <div className="space-y-1.5 text-center">
          <Eyebrow>{isSignUp ? "PCRSTUDIO · NEW WORKSPACE" : "PCRSTUDIO · WELCOME BACK"}</Eyebrow>
          <CardTitle className="font-serif text-2xl font-semibold tracking-tight text-foreground sm:text-2xl">
            {isSignUp ? "Make your bench a little clearer" : "Welcome back to your bench"}
          </CardTitle>
          <CardDescription className="mx-auto max-w-[36ch] text-start text-sm leading-relaxed text-muted-foreground">
            {isSignUp
              ? "Create a free workspace for your sequences, design decisions, and reproducible runs."
              : "Sign in to pick up your projects, settings, and saved designs exactly where you left them."}
          </CardDescription>
        </div>
      </CardHeader>

      <CardContent className="space-y-4 pt-4">
        {notice ? (
          <div className="animate-fade-in" role="status">
            <Alert className="border-border/50 bg-surface-wash/55 text-sm">
              <AlertDescription className="text-muted-foreground">{notice}</AlertDescription>
            </Alert>
          </div>
        ) : null}

        {/* Rate limit warning banner */}
        {state.error && isRateLimited(state) && (
          <div className="animate-fade-in" role="alert">
            <Alert variant="destructive" className="border-destructive/30 bg-destructive/5 text-sm">
              <AlertCircle className="size-4 shrink-0" aria-hidden="true" />
              <AlertDescription className="flex-1">
                Too many attempts. Please wait a moment before trying again.
              </AlertDescription>
            </Alert>
          </div>
        )}

        <form
          action={formAction}
          className="space-y-3"
          data-form-ready={mounted ? "true" : undefined}
        >
          <input type="hidden" name="next" value={next} />

          {isSignUp ? (
            <Field
              label="Name"
              name="displayName"
              autoComplete="name"
              required
              maxLength={80}
              placeholder="Ada Lovelace"
            />
          ) : null}

          <Field
            label="Email"
            name="email"
            type="email"
            autoComplete="email"
            required
            placeholder="you@lab.example"
          />

          <Field
            label="Password"
            name="password"
            type="password"
            autoComplete={isSignUp ? "new-password" : "current-password"}
            required
            minLength={isSignUp ? 10 : undefined}
            maxLength={isSignUp ? 256 : undefined}
            hint={
              isSignUp
                ? "Use at least 10 characters. A memorable phrase is usually stronger than a short scramble."
                : undefined
            }
            showStrength={isSignUp}
          />

          {isSignUp ? null : (
            <label className="flex cursor-pointer items-center gap-2.5 text-sm text-muted-foreground transition-colors hover:text-foreground">
              {/* Checked by default: most people on their own machine want to
                  stay signed in, and unchecking is the deliberate act. */}
              <input
                type="checkbox"
                name="remember"
                defaultChecked
                className="size-4 rounded border-input accent-primary transition-colors focus-visible:ring-2 focus-visible:ring-ring/50"
              />
              Keep me signed in on this device
            </label>
          )}

          <FormFeedback state={state} />

          <div className="border-t border-border/40 pt-3">
            <SubmitButton
              pending={pending}
              className="w-full"
              pendingLabel={isSignUp ? "Creating account…" : "Signing in…"}
            >
              {isSignUp ? "Create account" : "Sign in"}
            </SubmitButton>
          </div>

          <div className="space-y-3 border-t border-border/40 pt-3">
            <p className="text-center text-sm text-muted-foreground">
              {isSignUp ? "Already have an account? " : "No account yet? "}
              <Link
                href={
                  next && next !== "/"
                    ? `${isSignUp ? "/sign-in" : "/sign-up"}?next=${encodeURIComponent(next)}`
                    : isSignUp
                      ? "/sign-in"
                      : "/sign-up"
                }
                className="font-medium text-primary underline underline-offset-4 transition-colors hover:text-primary/80"
              >
                {isSignUp ? "Sign in" : "Create one"}
              </Link>
            </p>

            {/* Where somebody was heading survives the trip between these two
                pages. Losing it is how a person signs up and lands on a
                dashboard, wondering what happened to the module they clicked. */}
            {/* The link somebody needs at exactly the moment they cannot get in.
                Hidden on the sign-up page, where it would be an offer to recover
                an account that does not exist yet. */}
            {!isSignUp && (
              <div className="space-y-3">
                <Separator className="relative" />
                <p className="text-center text-sm text-muted-foreground">
                  <Link
                    href="/recover"
                    className="font-medium text-primary underline underline-offset-4 transition-colors hover:text-primary/80"
                  >
                    Forgot your password?
                  </Link>
                </p>
              </div>
            )}

            <p className="text-center text-xs leading-relaxed text-muted-foreground">
              {isSignUp
                ? "No marketing emails and no verification step. Just an account for keeping your work yours."
                : "Your projects and saved designs will be waiting where you left them."}
            </p>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

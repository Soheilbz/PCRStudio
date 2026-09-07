"use client";

import {
  Download,
  Upload,
  LogOut,
  MonitorSmartphone,
  ShieldCheck,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import { useActionState, useRef, useState } from "react";
import { toast } from "sonner";

import { Field, FormFeedback, SubmitButton } from "@/components/form-parts";
import { LocalTime } from "@/components/local-time";
import { Button } from "@/components/ui/button";
import { RecoveryCodePanel } from "@/components/auth/recovery-code";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  changeEmailAction,
  changePasswordAction,
  deleteAccountAction,
  endAllSessionsAction,
  renameAction,
  reissueRecoveryCodeAction,
  signOutAction,
  type FormState,
} from "@/lib/auth/actions";
import type { Imported, RecoveryStatus, User } from "@/lib/api/types";
import { inMegabytes, MAX_ACCOUNT_IMPORT_BYTES } from "@/lib/limits";

const EMPTY: FormState = {};
type RecoveryCardStatus = RecoveryStatus | { unavailable: true };

export function ProfileForm({ user }: { user: User }) {
  const [state, formAction, pending] = useActionState(renameAction, EMPTY);

  return (
    <Card className="workbench-card">
      <CardHeader>
        <CardTitle className="font-serif text-lg font-semibold">Profile</CardTitle>
        <CardDescription>How you appear in PCRStudio.</CardDescription>
      </CardHeader>
      <CardContent>
        <form action={formAction} className="max-w-md space-y-3.5">
          <Field
            label="Name"
            name="displayName"
            defaultValue={user.displayName}
            required
            maxLength={80}
            autoComplete="name"
          />
          <div className="space-y-1.5">
            <p className="text-sm font-medium">Sign-in email</p>
            <p className="font-mono text-sm break-all text-muted-foreground">{user.email}</p>
          </div>
          <FormFeedback state={state} />
          <SubmitButton pending={pending} pendingLabel="Saving…">
            Save
          </SubmitButton>
        </form>
      </CardContent>
    </Card>
  );
}

export function EmailForm({ user }: { user: User }) {
  const [state, formAction, pending] = useActionState(changeEmailAction, EMPTY);

  return (
    <Card className="workbench-card">
      <CardHeader>
        <CardTitle className="font-serif text-lg font-semibold">Sign-in email</CardTitle>
        <CardDescription>
          Changing your login address requires your password and signs out every other browser.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form action={formAction} className="max-w-md space-y-3.5">
          <Field
            label="New email"
            name="newEmail"
            type="email"
            defaultValue={user.email}
            autoComplete="email"
            required
          />
          <Field
            label="Current password"
            name="currentPassword"
            type="password"
            autoComplete="current-password"
            required
          />
          <FormFeedback state={state} />
          <SubmitButton pending={pending} pendingLabel="Changing…">
            Change email
          </SubmitButton>
        </form>
      </CardContent>
    </Card>
  );
}

export function PasswordForm() {
  const [state, formAction, pending] = useActionState(changePasswordAction, EMPTY);

  return (
    <Card className="workbench-card">
      <CardHeader>
        <CardTitle className="font-serif text-lg font-semibold">Password</CardTitle>
        <CardDescription>
          Changing it signs out every other browser, and keeps this one.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form action={formAction} className="max-w-md space-y-3.5">
          <Field
            label="Current password"
            name="currentPassword"
            type="password"
            autoComplete="current-password"
            required
          />
          <Field
            label="New password"
            name="newPassword"
            type="password"
            autoComplete="new-password"
            required
            minLength={10}
            maxLength={256}
            hint="At least 10 characters."
          />
          <Field
            label="New password again"
            name="confirmPassword"
            type="password"
            autoComplete="new-password"
            required
            minLength={10}
            maxLength={256}
          />
          <FormFeedback state={state} />
          <SubmitButton pending={pending} pendingLabel="Changing…">
            Change password
          </SubmitButton>
        </form>
      </CardContent>
    </Card>
  );
}

export function SessionsCard() {
  const [everywhere, everywhereAction, everywherePending] = useActionState(
    endAllSessionsAction,
    EMPTY,
  );

  return (
    <Card className="workbench-card">
      <CardHeader>
        <CardTitle className="font-serif text-lg font-semibold">Sessions</CardTitle>
        <CardDescription>
          A remembered sign-in can stay open for up to thirty days; ordinary browser sessions expire
          sooner.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-2">
        <form action={signOutAction}>
          <Button type="submit" variant="outline" size="sm">
            <LogOut />
            Sign out here
          </Button>
        </form>
        <form action={everywhereAction} className="space-y-2">
          <Button type="submit" variant="outline" size="sm" disabled={everywherePending}>
            <MonitorSmartphone />
            {everywherePending ? "Signing out…" : "Sign out everywhere"}
          </Button>
          <FormFeedback state={everywhere} />
        </form>
      </CardContent>
    </Card>
  );
}

export function DeleteAccountCard({ user }: { user: User }) {
  const [state, formAction, pending] = useActionState(deleteAccountAction, EMPTY);

  return (
    <Card className="workbench-card border-destructive/40">
      <CardHeader>
        <CardTitle className="font-serif text-lg font-semibold text-destructive">
          Delete this account
        </CardTitle>
        <CardDescription>
          The account and every session it has are removed immediately. This cannot be undone.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form action={formAction} className="max-w-md space-y-3.5">
          <Field
            label="Password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
          />
          <Field
            label="Type your email to confirm"
            name="confirm"
            required
            placeholder={user.email}
            autoComplete="off"
          />
          <FormFeedback state={state} />
          <SubmitButton pending={pending} variant="destructive" pendingLabel="Deleting…">
            <Trash2 />
            Delete account
          </SubmitButton>
        </form>
      </CardContent>
    </Card>
  );
}

/**
 * The recovery code, from the account page.
 *
 * Two people reach this card. One made their account after recovery existed and
 * wants a fresh code because they lost the paper; the other made it before, has
 * none at all, and does not know that a forgotten password would end their
 * account. The second is why this card says what it says even when there is
 * nothing wrong.
 */
export function RecoveryCodeCard({ status }: { status: RecoveryCardStatus | null }) {
  const [state, formAction, pending] = useActionState(reissueRecoveryCodeAction, EMPTY);

  if (state.recoveryCode) {
    return (
      <RecoveryCodePanel
        code={state.recoveryCode}
        heading="Save your new recovery code"
        explanation={
          "This replaces any earlier code — the old one stopped working the moment this " +
          "one was made."
        }
      >
        <p className="text-xs leading-relaxed text-muted-foreground">
          Nothing else changed: you are still signed in, and your password is the same.
        </p>
      </RecoveryCodePanel>
    );
  }

  const unavailable = status !== null && "unavailable" in status;
  const missing = status !== null && !("unavailable" in status) && !status.hasCode;

  return (
    <Card className={missing ? "workbench-card border-warning/50 bg-warning/5" : "workbench-card"}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 font-serif text-lg font-semibold">
          {missing ? (
            <TriangleAlert className="size-4 text-warning" aria-hidden="true" />
          ) : (
            <ShieldCheck className="size-4 text-muted-foreground" aria-hidden="true" />
          )}
          Recovery code
        </CardTitle>
        <CardDescription>
          {unavailable
            ? "Recovery status is temporarily unavailable. Try again shortly; no change was made to your code."
            : missing
              ? "This account has no recovery code. There is no verification email here, so without one a forgotten password would end the account and everything in it."
              : "The one way back in if you forget your password. There is nothing to email you a reset link to, by design."}
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-3.5">
        {status && !unavailable && "issuedAt" in status && status.issuedAt ? (
          <p className="text-xs text-muted-foreground">
            The current code was issued <LocalTime iso={status.issuedAt} />. It cannot be shown
            again — making a new one is the only option, and it replaces the old one.
          </p>
        ) : null}

        <form action={formAction} className="max-w-md space-y-3.5">
          <Field
            label="Your password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            hint="Asked for so that an open session left on a shared machine cannot mint one."
          />

          <FormFeedback state={state} />

          <SubmitButton
            pending={pending}
            variant={missing ? "default" : "outline"}
            size="sm"
            pendingLabel="Making one…"
            disabled={unavailable}
          >
            {unavailable
              ? "Recovery status unavailable"
              : missing
                ? "Create a recovery code"
                : "Replace the recovery code"}
          </SubmitButton>
        </form>
      </CardContent>
    </Card>
  );
}

/**
 * Taking your own work out.
 *
 * Not a convenience feature. A tool that asks scientists to keep a year of
 * designs inside it and gives them no way to leave with them has taken their
 * work hostage, however good its intentions. This is the door.
 *
 * The export carries the request beside every result, so it is enough to
 * reproduce a design somewhere else rather than only to read what this one
 * said — the same argument the provenance block makes for a single run, made
 * for the whole account.
 */
export function ExportCard() {
  return (
    <Card className="workbench-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 font-serif text-lg font-semibold">
          <Download className="size-4 text-muted-foreground" aria-hidden="true" />
          Your data
        </CardTitle>
        <CardDescription>
          Every project and every saved run, with the request that produced each result — enough to
          rebuild a design elsewhere, not just to read it.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-3">
        <Button
          variant="outline"
          size="sm"
          nativeButton={false}
          render={<a href="/account/data/export" />}
        >
          <Download />
          Download everything
        </Button>

        <p className="text-xs leading-relaxed text-muted-foreground">
          Your password and recovery code are not in it. Both are stored hashed, so there is nothing
          to export.
        </p>

        <ImportControl />
      </CardContent>
    </Card>
  );
}

/**
 * The other half of the export.
 *
 * Without this the download was a one-way door: somebody could take their work
 * out and never put it back — not into a new account, not into their own copy
 * of a tool whose whole licence is that they may run one. A backup nothing can
 * restore is a file.
 *
 * It lives inside the same card rather than beside it, because "your data" is
 * one subject and splitting it into two panels would suggest they are separate
 * features rather than two directions of the same one.
 */
function ImportControl() {
  const chooser = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [said, setSaid] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  const take = (file: File) => {
    if (file.size > MAX_ACCOUNT_IMPORT_BYTES) {
      const message = `That export is larger than ${inMegabytes(MAX_ACCOUNT_IMPORT_BYTES)}. Choose a smaller PCRStudio export.`;
      setSaid(null);
      setFailed(message);
      toast.error("Import failed", { description: message });
      if (chooser.current) chooser.current.value = "";
      return;
    }

    setBusy(true);
    setSaid(null);
    setFailed(null);

    void fetch("/account/data/import", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: file,
    })
      .then(async (response) => {
        const payload = (await response.json().catch(() => null)) as
          (Imported & { error?: never }) | { error?: string; detail?: string } | null;
        if (!response.ok || !payload || !("projects" in payload)) {
          const message =
            payload && !("projects" in payload)
              ? (payload.error ?? payload.detail ?? "Nothing came back. Try again.")
              : "Nothing came back. Try again.";
          throw new Error(message);
        }
        return payload;
      })
      .then((answer) => {
        const { projects, runs, alreadyHere, restored, refused } = answer;
        const sentence =
          [
            projects > 0
              ? `${projects} project${projects === 1 ? "" : "s"} brought in with ${runs} run${runs === 1 ? "" : "s"}.`
              : null,
            // First, because somebody importing a backup after deleting
            // something by mistake is looking for exactly this sentence.
            restored > 0
              ? `${restored} deleted project${restored === 1 ? " was" : "s were"} brought back.`
              : null,
            // Said plainly rather than hidden: somebody who clicks twice
            // should be told why the second time did nothing, or they will
            // conclude it failed.
            alreadyHere > 0
              ? `${alreadyHere} ${alreadyHere === 1 ? "was" : "were"} already here and left alone.`
              : null,
            refused > 0 ? `${refused} did not fit under the project limit.` : null,
          ]
            .filter(Boolean)
            .join(" ") || "Nothing in that file was new.";
        setSaid(sentence);
        toast.success("Import finished", { description: sentence });
      })
      .catch((cause: unknown) => {
        const message =
          cause instanceof Error && cause.message
            ? cause.message
            : "The file could not be read. Choose a valid PCRStudio JSON export.";
        setFailed(message);
        toast.error("Import failed", { description: message });
      })
      .finally(() => {
        setBusy(false);
        // So the same file can be chosen again after a failure; without this
        // the input holds the old value and the change event never fires.
        if (chooser.current) chooser.current.value = "";
      });
  };

  return (
    <div className="space-y-2 border-t pt-3">
      <input
        ref={chooser}
        id="account-import-file"
        type="file"
        accept="application/json,.json"
        aria-label="Choose a PCRStudio JSON export to import"
        className="sr-only"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) take(file);
        }}
      />
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={busy}
        onClick={() => chooser.current?.click()}
      >
        <Upload />
        {busy ? "Reading…" : "Bring an export back in"}
      </Button>

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

      <p className="text-xs leading-relaxed text-muted-foreground">
        Importing the same file twice changes nothing the second time, so it is safe to try when you
        are not sure whether the first one worked.
      </p>
    </div>
  );
}

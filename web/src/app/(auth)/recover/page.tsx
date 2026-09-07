import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { RecoverForm } from "@/components/auth/recover-form";
import { currentUser } from "@/lib/auth/current-user";
import { pendingCodeFlagIsValid } from "@/lib/auth/session";

export const metadata: Metadata = {
  title: "Use a recovery code",
  description: "Set a new password with the recovery code from when you created your account.",
  // Not a page for search results: it is reached from the sign-in page by
  // somebody who already has an account, and indexing it invites people who do
  // not into a form that cannot help them.
  robots: { index: false, follow: false },
};

export default async function Page() {
  // Somebody already signed in does not need this, and offering it would mean
  // offering to end every session they are currently using — except the one
  // who has just used a code: recoverAction flagged that, and this render may
  // be the refresh whose whole job is showing its replacement.
  if ((await currentUser()) && !(await pendingCodeFlagIsValid())) redirect("/account");

  return <RecoverForm />;
}

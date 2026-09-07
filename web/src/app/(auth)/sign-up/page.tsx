import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { CredentialsForm } from "@/components/auth/credentials-form";
import { currentUser } from "@/lib/auth/current-user";
import { isSafeDestination } from "@/lib/auth/destination";
import { pendingCodeFlagIsValid } from "@/lib/auth/session";

export const metadata: Metadata = {
  title: "Create an account",
  description: "Create a PCRStudio account.",
  robots: { index: false, follow: true },
};

export default async function Page({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  // Someone already signed in has no business on this page — unless they have
  // just created the account and the code panel is what this render exists to
  // show. signUpAction flags exactly that; without the exception the refresh
  // that follows its cookie write would redirect before anything renders.
  if ((await currentUser()) && !(await pendingCodeFlagIsValid())) redirect("/");

  const { next } = await searchParams;
  // Checked before it reaches the client component, so an off-site value can
  // never end up in a link there.
  const destination = next && isSafeDestination(next) ? next : "/";
  return <CredentialsForm mode="sign-up" next={destination} />;
}

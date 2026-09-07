import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { CredentialsForm } from "@/components/auth/credentials-form";
import { currentUser } from "@/lib/auth/current-user";
import { isSafeDestination } from "@/lib/auth/destination";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to PCRStudio.",
  robots: { index: false, follow: true },
};

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ next?: string; signedOut?: string }>;
}) {
  // Someone already signed in has no business on this page.
  if (await currentUser()) redirect("/");

  const { next, signedOut } = await searchParams;
  // Checked before it reaches the client component, so an off-site value can
  // never end up in a link there.
  const destination = next && isSafeDestination(next) ? next : "/";
  return (
    <CredentialsForm
      mode="sign-in"
      next={destination}
      // Saying it happened is the difference between a sign-out that worked and
      // a session that expired without telling anybody.
      notice={signedOut ? "You are signed out. Your projects are still here." : undefined}
    />
  );
}

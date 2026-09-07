import { currentUser } from "@/lib/auth/current-user";
import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { pendingCodeFlagIsValid } from "@/lib/auth/session";
import AuthClientLayout from "./client-layout";

export default async function AuthServerLayout({ children }: { children: React.ReactNode }) {
  // Signed-in visitors are bounced out — except the one whose recovery code
  // was just minted and is on screen. The page guards carry the same
  // exception; without it here, the framework's post-action refresh hits this
  // layout first and redirects before the panel ever renders.
  if ((await currentUser()) && !(await pendingCodeFlagIsValid())) {
    const pathname = (await headers()).get("x-pcr-pathname") ?? "";
    redirect(pathname === "/recover" ? "/account" : "/");
  }

  return <AuthClientLayout>{children}</AuthClientLayout>;
}

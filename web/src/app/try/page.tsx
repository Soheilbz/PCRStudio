import type { Metadata } from "next";

import { AppFooter } from "@/components/layout/app-footer";
import { PublicHeader } from "@/components/layout/public-header";
import { TryIt } from "@/components/try/try-it";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Try it without an account",
  description:
    "Paste a sequence and get a designed primer pair, with everything that was measured to choose it. No account, nothing saved.",
  alternates: { canonical: "/try" },
};

/** The anonymous path from a sequence to a readable primer result. */
export default function TryPage() {
  return (
    <div className="workbench-shell flex min-h-svh flex-col bg-background">
      <PublicHeader />
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 sm:py-10 lg:px-8 lg:py-12">
        <div className="space-y-6">
          <div className="workbench-hero max-w-2xl space-y-1.5 rounded-2xl px-5 py-4 sm:px-6">
            <h1 className="font-serif text-2xl font-semibold tracking-tight text-balance sm:text-3xl">
              Try it without an account
            </h1>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Paste a sequence and {site.name} will design a pair for it and show everything it
              measured to choose them. Nothing is saved and nothing is asked of you.
            </p>
          </div>

          <TryIt />
        </div>
      </main>
      <AppFooter />
    </div>
  );
}

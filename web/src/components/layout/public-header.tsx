import { Dna, LogIn } from "lucide-react";
import Link from "next/link";

import { ThemeToggle } from "@/components/theme/theme-toggle";

/** The quiet, signed-out frame shared by public information and try-it pages. */
export function PublicHeader() {
  return (
    <header className="border-b border-border/60 bg-surface-wash/75 backdrop-blur-md">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
        <Link
          href="/sign-in"
          className="flex items-center gap-2.5 rounded-lg focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          <span className="flex size-8 items-center justify-center rounded-lg bg-brand text-brand-foreground">
            <Dna className="size-4" aria-hidden="true" />
          </span>
          <span className="grid leading-tight">
            <span className="font-serif text-sm font-semibold tracking-tight">PCRStudio</span>
            <span className="hidden text-xs text-muted-foreground sm:block">
              Primer design, made legible
            </span>
          </span>
        </Link>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Link
            href="/sign-in"
            className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-primary px-3 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <LogIn className="size-3.5" aria-hidden="true" />
            Back to sign in
          </Link>
        </div>
      </div>
    </header>
  );
}

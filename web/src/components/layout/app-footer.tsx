import Link from "next/link";
import { ArrowUpRight, CircleUserRound, LogIn } from "lucide-react";

import { site } from "@/lib/site";

const FOOTER_LINKS = [
  ["About", "/about"],
  ["Documentation", "/docs"],
  ["Privacy", "/privacy"],
  ["Terms", "/terms"],
  ["Contact", "/contact"],
] as const;

export function AppFooter({ signedIn = false }: { signedIn?: boolean }) {
  return (
    <footer className="border-t border-border/60 bg-surface-wash/45">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-5 gap-y-2 px-5 py-3 text-xs text-muted-foreground sm:px-6 lg:px-8">
        <p className="mr-auto max-w-full sm:whitespace-nowrap">
          {site.name} — {site.tagline}. Proprietary software.
        </p>
        <nav
          aria-label="About this site"
          className="flex flex-wrap items-center gap-x-4 gap-y-1 sm:border-l sm:border-border/60 sm:pl-5"
        >
          {FOOTER_LINKS.map(([label, href]) => (
            <Link key={href} href={href} className="transition-colors hover:text-foreground">
              {label}
            </Link>
          ))}
          <a
            href={site.repository}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-1 transition-colors hover:text-foreground"
          >
            Source <ArrowUpRight className="size-3" aria-hidden="true" />
          </a>
        </nav>
        {signedIn ? (
          <Link
            href="/account"
            className="inline-flex items-center gap-1.5 font-medium text-primary transition-colors hover:text-primary/80 hover:underline hover:underline-offset-4 sm:whitespace-nowrap"
          >
            <CircleUserRound className="size-3.5" aria-hidden="true" />
            Account settings
          </Link>
        ) : (
          <Link
            href="/sign-in"
            className="inline-flex items-center gap-1.5 font-medium text-primary transition-colors hover:text-primary/80 hover:underline hover:underline-offset-4 sm:whitespace-nowrap"
          >
            <LogIn className="size-3.5" aria-hidden="true" />
            Back to sign in
          </Link>
        )}
      </div>
    </footer>
  );
}

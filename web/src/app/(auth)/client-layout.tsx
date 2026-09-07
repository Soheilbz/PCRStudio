"use client";

import Link from "next/link";
import {
  ArrowUpRight,
  BookOpen,
  Dna,
  FlaskConical,
  RefreshCw,
  Search,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { Eyebrow, HelixDrift } from "@/components/auth/bench";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { site } from "@/lib/site";
import { cn } from "@/lib/utils";

export default function AuthLayout({ children }: { children: ReactNode }) {
  const [mounted, setMounted] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setMounted(true), 0);
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      clearTimeout(timer);
      window.removeEventListener("scroll", handleScroll);
    };
  }, []);

  const footerLinks = [
    { href: "/about", label: "About PCRStudio" },
    { href: "/docs", label: "Documentation" },
    { href: "/privacy", label: "Privacy" },
    { href: "/terms", label: "Terms" },
    { href: "/contact", label: "Support" },
  ];

  return (
    <div className="auth-shell flex min-h-svh flex-col overflow-hidden bg-background">
      <a
        href="#auth-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-lg focus:bg-surface-wash focus:px-4 focus:py-2 focus:text-sm focus:shadow-lg"
      >
        Skip to sign in
      </a>
      <header
        className={cn(
          "relative z-20 flex items-center justify-between border-b px-5 py-3 transition-all duration-300 sm:px-8",
          "border-border/60 bg-surface-wash/75 backdrop-blur-md",
          scrolled && "border-border/90 bg-surface-wash/95 shadow-sm",
        )}
      >
        <div className="flex items-center gap-3">
          <span className="flex size-9 items-center justify-center rounded-xl bg-brand text-brand-foreground shadow-sm">
            <Dna className="size-4.5" aria-hidden="true" />
          </span>
          <span className="grid leading-tight">
            <span className="font-serif text-base font-semibold tracking-tight">PCRStudio</span>
            <span className="text-xs text-muted-foreground">Primer design, made legible</span>
          </span>
        </div>
        <ThemeToggle />
      </header>

      <main
        id="auth-content"
        className="relative flex flex-1 items-center justify-center px-5 py-10 sm:px-8 lg:py-14"
      >
        <div className="auth-orb auth-orb-coral" aria-hidden="true" />
        <div className="auth-orb auth-orb-lilac" aria-hidden="true" />
        <div className="auth-orb auth-orb-sage" aria-hidden="true" />
        <div className="relative grid w-full max-w-5xl items-center gap-12 lg:grid-cols-[1.05fr_0.95fr] lg:gap-16">
          <section className="relative hidden lg:block" aria-labelledby="auth-heading">
            <div className="absolute -inset-12 -z-10 opacity-35" aria-hidden="true">
              <HelixDrift className="h-full w-full" />
            </div>
            <div
              className="animate-fade-in-up relative space-y-7"
              style={{ animationDelay: mounted ? "0ms" : "200ms" }}
            >
              <div className="space-y-3">
                <Eyebrow>PCRSTUDIO · PRIVATE WORKSPACE</Eyebrow>
                <h1
                  id="auth-heading"
                  className="max-w-xl font-serif text-4xl leading-[1.08] tracking-tight text-balance text-foreground xl:text-5xl"
                >
                  A clearer way to design primers.
                </h1>
                <p className="max-w-lg text-base leading-relaxed text-muted-foreground">
                  Keep the sequence, the constraints, and the reasoning together. PCRStudio turns
                  primer design into a record you can inspect, share, and reproduce.
                </p>
              </div>

              <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                <span className="rounded-full border border-primary/20 bg-surface-wash/55 px-3 py-1.5">
                  Transparent constraints
                </span>
                <span className="rounded-full border border-primary/20 bg-surface-wash/55 px-3 py-1.5">
                  Reproducible runs
                </span>
                <span className="rounded-full border border-primary/20 bg-surface-wash/55 px-3 py-1.5">
                  11 design systems
                </span>
              </div>

              <ol className="space-y-3" role="list">
                <EnhancedStep
                  n="01"
                  title="Keep your place"
                  description="Projects remember the target, settings, and every run, so a closed tab never means starting over."
                  icon={BookOpen}
                />
                <EnhancedStep
                  n="02"
                  title="See the reasoning"
                  description="Every candidate comes with the constraints it passed, the ones it missed, and what to try next."
                  icon={Search}
                />
                <EnhancedStep
                  n="03"
                  title="Make it reproducible"
                  description="Store the model and parameters beside the primers, ready for review, ordering, or publication."
                  icon={RefreshCw}
                />
              </ol>

              <div className="flex items-center gap-3 font-mono text-xs tracking-wider text-muted-foreground/80">
                <FlaskConical className="size-4 text-primary" aria-hidden="true" />
                <span>5′-ATG CGT TAC GGA CCT GAA T-3′ · 20 nt · Tm 61.4 °C</span>
              </div>
            </div>
          </section>

          <div
            className="animate-fade-in w-full"
            style={{ animationDelay: mounted ? "100ms" : "300ms" }}
          >
            {children}
          </div>
        </div>
      </main>

      <footer className="relative z-10 border-t border-border/50 bg-surface-wash/50 px-5 py-4 sm:px-8">
        <nav
          className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs text-muted-foreground"
          aria-label="Footer navigation"
        >
          {footerLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="transition-colors hover:text-foreground hover:underline hover:underline-offset-4"
            >
              {link.label}
            </Link>
          ))}
          <a
            href={site.repository}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-1 transition-colors hover:text-foreground hover:underline hover:underline-offset-4"
          >
            Source on GitHub <ArrowUpRight className="size-3" aria-hidden="true" />
          </a>
        </nav>
        <p className="mt-2 flex items-center justify-center gap-1 text-center text-xs text-muted-foreground/70">
          <ShieldCheck className="size-3" aria-hidden="true" /> Your workspace stays yours.
        </p>
      </footer>
    </div>
  );
}

function EnhancedStep({
  n,
  title,
  description,
  icon: Icon,
}: {
  n: string;
  title: string;
  description: string;
  icon: typeof BookOpen;
}) {
  return (
    <li className="group rounded-xl border border-border/50 bg-surface-wash/45 p-3.5 transition-all duration-300 hover:border-primary/30 hover:bg-surface-warm/35 hover:shadow-sm">
      <div className="flex items-start gap-3">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 font-mono text-xs font-medium text-primary">
          {n}
        </span>
        <div className="min-w-0 flex-1 space-y-1">
          <p className="font-serif text-sm font-semibold text-foreground">{title}</p>
          <p className="text-sm leading-relaxed text-muted-foreground">{description}</p>
        </div>
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-surface-warm/35 text-muted-foreground/60 transition-colors group-hover:bg-primary/10 group-hover:text-primary">
          <Icon className="size-4" aria-hidden="true" />
        </span>
      </div>
    </li>
  );
}

import type { Metadata } from "next";
import Link from "next/link";

import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Mail, ExternalLink, Link2 } from "lucide-react";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Contact & Support",
  description: "Get help, report issues, or suggest features for PCRStudio.",
};

export default function ContactPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Contact & Support"
        description="Get help, report issues, or suggest features. We read every message."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="workbench-card lg:col-span-1">
          <CardHeader>
            <CardTitle className="font-serif text-lg font-semibold">Ways to reach us</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-start gap-3 rounded-xl border border-border/60 bg-surface-wash/35 p-4 transition-colors hover:border-primary/30 hover:bg-surface-warm/25">
              <div
                className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"
                aria-hidden="true"
              >
                <Mail className="size-5" />
              </div>
              <div>
                <h3 className="font-serif text-sm font-semibold text-foreground">Email</h3>
                <p className="text-sm text-muted-foreground">
                  Best for: bugs, feature requests, security issues, general questions
                </p>
                <Button
                  variant="default"
                  size="sm"
                  className="mt-2"
                  render={<a href="mailto:support@pcrstudio.dev" />}
                >
                  <Mail className="mr-1.5 size-3.5" aria-hidden="true" />
                  support@pcrstudio.dev
                </Button>
              </div>
            </div>

            <div className="flex items-start gap-3 rounded-xl border border-border/60 bg-surface-wash/35 p-4 transition-colors hover:border-primary/30 hover:bg-surface-warm/25">
              <div
                className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"
                aria-hidden="true"
              >
                <Link2 className="size-5" />
              </div>
              <div>
                <h3 className="font-serif text-sm font-semibold text-foreground">GitHub Issues</h3>
                <p className="text-sm text-muted-foreground">
                  Best for: bug reports, feature requests, code contributions
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-2"
                  render={
                    <a
                      href={`${site.repository}/issues`}
                      target="_blank"
                      rel="noreferrer noopener"
                    />
                  }
                >
                  <Link2 className="mr-1.5 size-3.5" aria-hidden="true" />
                  Open an issue
                  <ExternalLink className="ml-1.5 size-3.5" aria-hidden="true" />
                </Button>
              </div>
            </div>

            <div className="flex items-start gap-3 rounded-xl border border-border/60 bg-surface-wash/35 p-4 transition-colors hover:border-primary/30 hover:bg-surface-warm/25">
              <div
                className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"
                aria-hidden="true"
              >
                <Link2 className="size-5" />
              </div>
              <div>
                <h3 className="font-serif text-sm font-semibold text-foreground">
                  GitHub Discussions
                </h3>
                <p className="text-sm text-muted-foreground">
                  Best for: questions, ideas, community discussion, showing your work
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-2"
                  render={
                    <a
                      href={`${site.repository}/discussions`}
                      target="_blank"
                      rel="noreferrer noopener"
                    />
                  }
                >
                  <Link2 className="mr-1.5 size-3.5" aria-hidden="true" />
                  Join discussion
                  <ExternalLink className="ml-1.5 size-3.5" aria-hidden="true" />
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="workbench-card lg:col-span-1">
          <CardHeader>
            <CardTitle className="font-serif text-lg font-semibold">Before you write</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm leading-relaxed text-muted-foreground">
            <div className="space-y-3">
              <h4 className="font-serif font-semibold text-foreground">Check the docs first</h4>
              <p>
                Many questions are answered in the{" "}
                <Link
                  href="/docs"
                  className="text-primary underline underline-offset-2 hover:text-primary/80"
                >
                  documentation
                </Link>{" "}
                — especially the{" "}
                <Link
                  href="/docs/guides"
                  className="text-primary underline underline-offset-2 hover:text-primary/80"
                >
                  design guides
                </Link>{" "}
                and{" "}
                <Link
                  href="/docs/limits"
                  className="text-primary underline underline-offset-2 hover:text-primary/80"
                >
                  rate limits
                </Link>{" "}
                pages.
              </p>
            </div>
            <div className="space-y-3">
              <h4 className="font-serif font-semibold text-foreground">For bug reports, include</h4>
              <ul className="ml-4 list-inside list-disc space-y-1.5">
                <li>What you were trying to do</li>
                <li>What happened instead (error message, wrong result, etc.)</li>
                <li>Steps to reproduce</li>
                <li>Your browser and OS</li>
                <li>If possible, a minimal example sequence or project export</li>
              </ul>
            </div>
            <div className="space-y-3">
              <h4 className="font-serif font-semibold text-foreground">For feature requests</h4>
              <p>
                Describe the problem you&apos;re solving, not just the solution you want. The best
                features come from understanding the real use case.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="workbench-hero border-primary/40">
        <CardContent className="space-y-4 px-6 pt-6 pb-6 text-center">
          <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
            <span>PCRStudio is proprietary software; see the repository license.</span>
            <Button
              variant="ghost"
              size="sm"
              render={<a href={site.repository} target="_blank" rel="noreferrer noopener" />}
            >
              <Link2 className="mr-1 size-3.5" aria-hidden="true" />
              View source
              <ExternalLink className="ml-1 size-3.5" aria-hidden="true" />
            </Button>
          </div>
          <p className="text-sm text-muted-foreground">
            Access to this instance does not grant permission to copy, modify, host, or redistribute
            the source code.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
